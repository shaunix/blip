# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Pulse, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Pulse is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Pulse is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Pulse; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

import datetime
import Image
import math
import os
import os.path
import re
import shutil
import StringIO
import time
import urllib
import xml.dom.minidom

import pulse.graphs
import pulse.models as db
import pulse.scm
import pulse.parsers
import pulse.utils

synop = 'update information about documentation'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only documents with a matching identifier will be updated.'


checkouts = {}
def get_checkout (record, update=True):
    key = '::'.join(map(str, [record.scm_type, record.scm_server, record.scm_module, record.scm_branch, record.scm_path]))
    if not checkouts.has_key (key):
        checkouts[key] = pulse.scm.Checkout.from_record (record, update=update)
    return checkouts[key]


def update_document (doc, **kw):
    if doc.subtype == 'gdu-docbook':
        update_gdu_docbook (doc, **kw)
    elif doc.subtype == 'gtk-doc':
        update_gtk_doc (doc, **kw)
    else:
        pulse.utils.warn ('Skipping document %s with unknown type %s' % (doc.ident, doc.subtype))


def update_gdu_docbook (doc, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (doc, update=kw.get('update', True))

    # FIXME: we want to add "audience" for docs.  use that here
    cnt = db.Branch.objects.filter (type='Document',
                                    subtype__startswith='gdu-',
                                    parent=doc.parent)
    if cnt.count() == 1:
        doc.icon_name = doc.parent.icon_name
        doc.icon_dir = doc.parent.icon_dir

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_docbook_docfile (docfile, doc, **kw)

    translations = db.Branch.objects.filter (type='Translation', parent=doc)
    for translation in translations:
        pofile = os.path.join (checkout.directory, translation.scm_dir, translation.scm_file)
        process_docbook_pofile (pofile, doc, **kw)

    process_credits (doc, **kw)
    process_figures (doc, checkout, **kw)

    makedir = os.path.join (checkout.directory, os.path.dirname (doc.scm_dir))
    makefile = pulse.parsers.Automake (os.path.join (makedir, 'Makefile.am'))
    xmlfiles = []
    fnames = ([makefile['DOC_MODULE']+'.xml']  +
              makefile.get('DOC_INCLUDES', '').split() +
              makefile.get('DOC_ENTITIES', '').split() )
    for fname in (fnames):
        xmlfiles.append (fname)

    doc.data['xmlfiles'] = sorted (xmlfiles)

    files = [os.path.join (doc.scm_dir, f) for f in xmlfiles]
    revision = db.Revision.get_last_revision (branch=doc.parent, files=files)
    if revision != None:
        doc.mod_datetime = revision.datetime
        doc.mod_person = revision.person

    update_graph (doc, **kw)

    doc.save()


def update_graph (doc, **kw):
    now = datetime.datetime.now()
    thisweek = pulse.utils.weeknum (now)
    of = db.OutputFile.objects.filter (type='graphs', ident=doc.ident, filename='commits.png')
    try:
        of = of[0]
    except IndexError:
        of = None

    files = [os.path.join (doc.scm_dir, f) for f in doc.data.get ('xmlfiles', [])]
    if len(files) == 0: return

    revs = db.Revision.select_revisions (branch=doc.parent, files=files,
                                         weeknum__gt=(thisweek - 24))
    if of != None:
        if kw.get('timestamps', True):
            lastrev = of.data.get ('lastrev', None)
            weeknum = of.data.get ('weeknum', None)
            if weeknum == thisweek:
                rev = None
                if lastrev != None:
                    try:
                        rev = revs[0].id
                    except IndexError:
                        pass
                if lastrev == rev:
                    pulse.utils.log ('Skipping commit graph for %s' % doc.ident)
                    return
    else:
        of = db.OutputFile (type='graphs', ident=doc.ident, filename='commits.png', datetime=now)

    pulse.utils.log ('Creating commit graph for %s' % doc.ident)
    stats = [0] * 24
    revs = list(revs)
    for rev in revs:
        idx = rev.weeknum - thisweek + 23
        stats[idx] += 1
    score = pulse.utils.score (stats)
    doc.mod_score = score

    graph = pulse.graphs.BarGraph (stats, 10)
    graph.save (of.get_file_path())

    of.data['coords'] = zip (graph.get_coords(), stats, range(thisweek-23, thisweek+1))
    if len(revs) > 0:
        of.data['lastrev'] = revs[0].id
    of.data['weeknum'] = thisweek
    of.save()


def update_gtk_doc (doc, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (doc, update=kw.get('update', True))
    data = {}

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_docbook_docfile (docfile, doc, **kw)

    process_credits (doc, **kw)
    process_figures (doc, checkout, **kw)

    doc.save()


def process_docbook_docfile (docfile, doc, **kw):
    rel_scm = pulse.utils.relative_path (docfile, pulse.config.scm_dir)
    if not os.path.exists (docfile):
        pulse.utils.warn ('No such file %s' % rel_scm)
        return
    mtime = os.stat(docfile).st_mtime
    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    title = None
    abstract = None
    credits = []
    try:
        dom = xml.dom.minidom.parse (docfile)
    except Exception, e:
        pulse.utils.warn ('Failed to load file %s' % rel_scm)
        doc.error = str(e)
        doc.save()
        return
    doc.error = None
    for node in dom.documentElement.childNodes:
        if node.nodeType != node.ELEMENT_NODE:
            continue
        if node.tagName[-4:] == 'info':
            infonodes = node.childNodes[0:]
            i = 0
            while i < len(infonodes):
                infonode = infonodes[i]
                if infonode.nodeType != infonode.ELEMENT_NODE:
                    i += 1
                    continue
                if infonode.tagName == 'title':
                    if title == None:
                        title = strvalue (infonode)
                elif infonode.tagName == 'abstract' and infonode.getAttribute ('role') == 'description':
                    abstract = strvalue (infonode)
                elif infonode.tagName == 'authorgroup':
                    infonodes.extend (infonode.childNodes)
                elif infonode.tagName in ('author', 'editor', 'othercredit'):
                    cr_name, cr_email = personname (infonode)
                    maint = (infonode.getAttribute ('role') == 'maintainer')
                    credits.append ((cr_name, cr_email, infonode.tagName, maint))
                elif infonode.tagName == 'collab':
                    cr_name = None
                    for ch in infonode.childNodes:
                        if ch.nodeType == ch.ELEMENT_NODE and ch.tagName == 'collabname':
                            cr_name = strvalue (ch)
                    if cr_name != None:
                        maint = (infonode.getAttribute ('role') == 'maintainer')
                        credits.append ((cr_name, None, 'collab', maint))
                elif infonode.tagName in ('corpauthor', 'corpcredit'):
                    maint = (infonode.getAttribute ('role') == 'maintainer')
                    credits.append ((strvalue (infonode), None, infonode.tagName, maint))
                elif infonode.tagName == 'publisher':
                    cr_name = None
                    for ch in infonode.childNodes:
                        if ch.nodeType == ch.ELEMENT_NODE and ch.tagName == 'publishername':
                            cr_name = strvalue (ch)
                    if cr_name != None:
                        maint = (infonode.getAttribute ('role') == 'maintainer')
                        credits.append ((cr_name, None, 'publisher', maint))
                i += 1
        elif node.tagName == 'title':
            title = strvalue (node)
            break
    if title != None:
        doc.update (name=normalize(title))
    if abstract != None:
        doc.update (desc=normalize(abstract))

    doc.credits = credits

    imgs = dom.getElementsByTagName ('imagedata')
    doc.data['figures'] = []
    doc.data['screens'] = {}
    for img in imgs:
        if not img.hasAttribute ('fileref'): continue
        ref = img.getAttribute ('fileref')

        par = img.parentNode
        is_screenshot = False
        while par.nodeType == par.ELEMENT_NODE:
            if par.tagName == 'screenshot':
                is_screenshot = True
            if is_screenshot:
                if par.hasAttribute ('id'):
                    parid = par.getAttribute ('id')
                    doc.data['screens'].setdefault (parid, ref)
            par = par.parentNode
        if is_screenshot:
            doc.data['screens'].setdefault (None, ref)

        doc.data['figures'].append (ref)

    db.Timestamp.set_timestamp (rel_scm, mtime)


def process_docbook_pofile (pofile, doc, **kw):
    lang = os.path.basename(pofile)[:-3]
    if not hasattr (doc, 'figures_by_lang'):
        doc.figures_by_lang = {}
    doc.figures_by_lang[lang] = []
    for ref in doc.data.get ('figures', []):
        dref = os.path.join (os.path.dirname (pofile), ref)
        if os.path.exists (dref):
            doc.figures_by_lang[lang].append (ref)
   
    rel_scm = pulse.utils.relative_path (pofile, pulse.config.scm_dir)
    if not os.path.exists (pofile):
        pulse.utils.warn ('No such file %s' % rel_scm)
        return
    mtime = os.stat(pofile).st_mtime
    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    po = pulse.parsers.Po (pofile)
    if doc.name.has_key('C') and po.has_message (doc.name['C']):
        doc.update (name={lang : po.get_message_str (doc.name['C'])})
    if doc.desc.has_key('C') and po.has_message (doc.desc['C']):
        doc.update (desc={lang : po.get_message_str (doc.desc['C'])})

    db.Timestamp.set_timestamp (rel_scm, mtime)


def process_credits (doc, **kw):
    if not hasattr (doc, 'credits'):
        return
    rels = []
    for cr_name, cr_email, cr_type, cr_maint in doc.credits:
        ent = None
        if cr_email != None:
            ent = db.Entity.objects.filter (email=cr_email)
            try:
                ent = ent[0]
            except IndexError:
                ent = None
        if ent == None:
            ident = '/ghost/' + urllib.quote (cr_name.encode('utf-8'))
            ent = db.Entity.get_record (ident, 'Ghost')
            ent.update (name=cr_name)
            if cr_email != None:
                ent.email = cr_email
            ent.save()
        rel = db.DocumentEntity.set_related (doc, ent)
        if cr_type in ('author', 'corpauthor'):
            rel.author = True
        elif cr_type == 'editor':
            rel.editor = True
        elif cr_type == 'publisher':
            rel.publisher = True
        if cr_maint:
            rel.maintainer = True
        rel.save()
        rels.append (rel)
    doc.set_relations (db.DocumentEntity, rels)


def process_figures (doc, checkout, **kw):
    figures = doc.data.get ('figures', [])
    figures_by_lang = getattr (doc, 'figures_by_lang', {})
    figures_by_lang['C'] = figures
    ofs = list(db.OutputFile.objects.filter (type='figures', ident=doc.ident))
    ofs_by_lang = {}
    for of in ofs:
        ofs_by_lang.setdefault (of.subdir, [])
        ofs_by_lang[of.subdir].append (of)
    for lang in figures_by_lang.keys():
        ofs_by_lang.setdefault (lang, [])

    for lang in ofs_by_lang.keys():
        process_images_lang (doc, checkout, lang,
                             figures_by_lang.get(lang, []),
                             ofs_by_lang[lang],
                             **kw)


def process_images_lang (doc, checkout, lang, figs, ofs, **kw):
    indir = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    indir = os.path.dirname (os.path.dirname (indir))
    indir = os.path.join (indir, lang)
    ofs_by_source = {}
    for of in ofs:
        ofs_by_source[of.source] = of
    screen = doc.data.get('screens', {}).get(None, None)
    for ref in figs:
        of = ofs_by_source.pop (ref, None)
        if of == None:
            infile = os.path.join (indir, ref)
            of = db.OutputFile (type='figures', ident=doc.ident, subdir=lang,
                                filename=os.path.basename (ref), source=ref,
                                datetime=datetime.datetime.now())
            copy_image (infile, of)
        else:
            infile = os.path.join (indir, of.source)
            if kw.get('timestamps', True):
                mtime = os.stat(infile).st_mtime
                if mtime > time.mktime(of.datetime.timetuple()):
                    copy_image (infile, of)
            else:
                copy_image (infile, of)
        if ref == screen:
            doc.data.setdefault ('screenshot', {})
            doc.data['screenshot'][lang] = of.id
    for of in ofs_by_source.values():
        pulse.utils.log ('Deleting figure %s/%s' % (of.subdir, of.filename))
        os.remove (of.get_file_path())
        os.remove (of.get_file_path('thumbs'))
        of.delete()


def copy_image (infile, of):
    if not os.path.exists (infile):
        pulse.utils.warn ('Failed to copy figure %s' % of.filename)
        return
    pulse.utils.log ('Copying figure %s/%s' % (of.subdir, of.filename))
    outfile = of.get_file_path ()
    outdir = os.path.dirname (outfile)
    if not os.path.exists (outdir):
        os.makedirs (outdir)
    tfile = of.get_file_path ('thumbs')
    tdir = os.path.dirname (tfile)
    if not os.path.exists (tdir):
        os.makedirs (tdir)
    shutil.copyfile (infile, outfile)
    try:
        im = Image.open (infile)
        w, h = im.size
        im.thumbnail((120, 120), Image.ANTIALIAS)
        tw, th = im.size
        im.save (tfile, 'PNG')
    except IOError:
        # PIL doesn't do interlaced PNGs.  Process the image with
        # ImageMagick and pipe the result back.
        fd = os.popen ('convert "%s" -interlace none -' % infile)
        # We have to wrap with StringIO because Image.open expects the
        # file object to implement seek, which os.popen does not.
        im = Image.open(StringIO.StringIO(fd.read()))
        im.thumbnail((120, 120), Image.ANTIALIAS)
        tw, th = im.size
        im.save (tfile, 'PNG')
    of.datetime = datetime.datetime.now()
    of.data['width'] = w
    of.data['height'] = h
    of.data['thumb_width'] = tw
    of.data['thumb_height'] = th
    of.save()


################################################################################
## XML Utilities

def strvalue(node):
    s = ''
    for child in node.childNodes:
        if child.nodeType == child.TEXT_NODE:
            s += child.data
        elif child.nodeType == child.ELEMENT_NODE:
            s += strvalue (child)
    return s

def normalize (s):
    if s == None:
        return s
    return re.sub('\s+', ' ', s).strip()

def personname (node):
    name = [None, None, None, None, None]
    namestr = None
    email = None
    for child in node.childNodes:
        if child.nodeType != child.ELEMENT_NODE:
            continue
        if child.tagName == 'personname':
            namestr = personname(child)[0]
        elif child.tagName == 'email':
            email = strvalue (child)
        elif namestr == None:
            try:
                i = ['honorific', 'firstname', 'othername', 'surname', 'lineage'].index(child.tagName)
                if name[i] == None:
                    name[i] = strvalue (child)
            except:
                pass
    if namestr == None:
        while None in name:
            name.remove(None)
        namestr = ' '.join (name)
    return (normalize (namestr), normalize (email))


################################################################################
## main

def main (argv, options={}):
    update = not options.get ('--no-update', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix == None:
        docs = db.Branch.objects.filter (type='Document')
    elif prefix.startswith ('/mod/'):
        docs = db.Branch.objects.filter (type='Document',
                                         parent__ident__startswith=prefix)
    elif prefix.startswith ('/set'):
        docs = db.Branch.objects.filter (type='Document',
                                         parent__set_module_subjs__subj__ident__startswith=prefix)
    else:
        docs = db.Branch.objects.filter (type='Document',
                                         ident__startswith=prefix)

    for doc in list(docs):
        update_document (doc, update=update, timestamps=timestamps)
