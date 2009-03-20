# Copyright (c) 2006-2008  Shaun McCance  <shaunm@gnome.org>
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
import libxml2
import math
import os
import os.path
import re
import shutil
import StringIO
import time
import urllib

import pulse.db
import pulse.graphs
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

    doc.updated = datetime.datetime.utcnow ()


def update_gdu_docbook (doc, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (doc, update=kw.get('update', True))

    # FIXME: we want to add "audience" for docs.  use that here
    cnt = pulse.db.Branch.select (pulse.db.Branch.type == u'Document',
                                  pulse.db.Branch.subtype.like (u'gdu-%'),
                                  pulse.db.Branch.parent_ident == doc.parent_ident)
    if cnt.count() == 1:
        doc.icon_name = doc.parent.icon_name
        doc.icon_dir = doc.parent.icon_dir

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_docbook_docfile (docfile, doc, **kw)

    # Coercing into a list, because otherwise this result set stays open,
    # which causes locking issues with subsequent UPDATE commands under
    # SQLite.  Probably not a problem with other databases.  Upper bound
    # on this result set is the number of languages GNOME is translated
    # into.  Be mindful when doing this for larger result sets.
    translations = list(pulse.db.Branch.select (type=u'Translation', parent=doc))
    for translation in translations:
        pofile = os.path.join (checkout.directory, translation.scm_dir, translation.scm_file)
        process_docbook_pofile (pofile, doc, **kw)

    process_credits (doc, **kw)
    process_figures (doc, checkout, **kw)

    makedir = os.path.join (checkout.directory, os.path.dirname (doc.scm_dir))
    makefile = pulse.parsers.Automake (os.path.join (makedir, 'Makefile.am'))
    xmlfiles = []
    doc_module = makefile['DOC_MODULE']
    if doc_module == '@PACKAGE_NAME@':
        doc_module = doc.parent.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
    fnames = ([doc_module + '.xml']  +
              makefile.get('DOC_INCLUDES', '').split() +
              makefile.get('DOC_ENTITIES', '').split() )
    for fname in (fnames):
        xmlfiles.append (fname)

    doc.data['xmlfiles'] = sorted (xmlfiles)

    files = [os.path.join (doc.scm_dir, f) for f in xmlfiles]
    revision = pulse.db.Revision.get_last_revision (branch=doc.parent, files=files)
    if revision != None:
        doc.mod_datetime = revision.datetime
        doc.mod_person = revision.person

    files = [os.path.join (doc.scm_dir, f) for f in doc.data.get ('xmlfiles', [])]
    if len(files) == 0:
        doc.mod_score = 0
    else:
        pulse.pulsate.update_graphs (doc,
                                     {'branch' : doc.parent, 'files' : files},
                                     10,
                                     **kw)


def update_gtk_doc (doc, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (doc, update=kw.get('update', True))
    data = {}

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_docbook_docfile (docfile, doc, **kw)

    process_credits (doc, **kw)
    process_figures (doc, checkout, **kw)


def process_docbook_docfile (docfile, doc, **kw):
    rel_scm = pulse.utils.relative_path (docfile, pulse.config.scm_dir)
    if not os.path.exists (docfile):
        pulse.utils.warn ('No such file %s' % rel_scm)
        return
    mtime = os.stat(docfile).st_mtime
    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    title = None
    abstract = None
    credits = []
    try:
        ctxt = libxml2.newParserCtxt()
        xmldoc = ctxt.ctxtReadFile (docfile, None, 0)
        xmldoc.xincludeProcess()
        root = xmldoc.getRootElement()
    except Exception, e:
        pulse.utils.warn ('Failed to load file %s' % rel_scm)
        doc.error = str(e)
        return
    doc.error = None
    seen = 0
    releaselinks = []
    doc.data['status'] = 'none'
    for node in pulse.utils.xmliter (root):
        if node.type != 'element':
            continue
        if node.name[-4:] == 'info':
            seen += 1
            infonodes = list (pulse.utils.xmliter (node))
            i = 0
            while i < len(infonodes):
                infonode = infonodes[i]
                if infonode.type != 'element':
                    i += 1
                    continue
                if infonode.name == 'title':
                    if title == None:
                        title = infonode.getContent()
                elif infonode.name == 'abstract' and infonode.prop('role') == 'description':
                    abstract = infonode.getContent()
                elif infonode.name == 'releaseinfo':
                    if infonode.prop ('revision') == doc.parent.data.get ('series'):
                        doc.data['status'] = infonode.prop ('role')
                        for ch in pulse.utils.xmliter (infonode):
                            if ch.type == 'element' and ch.name == 'ulink':
                                releaselinks.append ((ch.prop ('type'), ch.prop ('url'), None))
                elif infonode.name == 'authorgroup':
                    infonodes.extend (list (pulse.utils.xmliter (infonode)))
                elif infonode.name in ('author', 'editor', 'othercredit'):
                    cr_name, cr_email = personname (infonode)
                    maint = (infonode.prop('role') == 'maintainer')
                    credits.append ((cr_name, cr_email, infonode.name, maint))
                elif infonode.name == 'collab':
                    cr_name = None
                    for ch in pulse.utils.xmliter (infonode):
                        if ch.type == 'element' and ch.name == 'collabname':
                            cr_name = normalize (ch.getContent())
                    if cr_name != None:
                        maint = (infonode.prop('role') == 'maintainer')
                        credits.append ((cr_name, None, 'collab', maint))
                elif infonode.name in ('corpauthor', 'corpcredit'):
                    maint = (infonode.prop('role') == 'maintainer')
                    credits.append ((normalize (infonode.getContent()), None, infonode.name, maint))
                elif infonode.name == 'publisher':
                    cr_name = None
                    for ch in pulse.utils.xmliter (infonode):
                        if ch.type == 'element' and ch.name == 'publishername':
                            cr_name = normalize (ch.getContent())
                    if cr_name != None:
                        maint = (infonode.prop('role') == 'maintainer')
                        credits.append ((cr_name, None, 'publisher', maint))
                i += 1
        elif node.name == 'title':
            seen += 1
            title = node.getContent()
        if seen > 1:
            break

    if title != None:
        doc.update (name=normalize(title))
    if abstract != None:
        doc.update (desc=normalize(abstract))

    oldlinks = {}
    for link in doc.data.get ('releaselinks', []):
        oldlinks[link[1]] = link[2]
    for i in range (len (releaselinks)):
        title = oldlinks.get (releaselinks[i][1], None)
        if title == None:
            title = pulse.utils.get_html_title (releaselinks[i][1])
        releaselinks[i] = (releaselinks[i][0], releaselinks[i][1], title)
    doc.data['releaselinks'] = releaselinks

    doc.credits = credits

    # FIXME
    imgs = xmldoc.xpathEval ('//imagedata')
    doc.data['figures'] = {}
    doc.data['screens'] = {}
    for img in imgs:
        fileref = img.prop ('fileref')
        if fileref == None:
            continue

        par = img.parent
        media = None
        is_screenshot = False
        while par.type == 'element':
            if par.name in ['mediaobject', 'inlinemediaobject']:
                media = par
            if par.name == 'screenshot':
                is_screenshot = True
            if is_screenshot:
                parid = par.prop ('id')
                if parid != None:
                    doc.data['screens'].setdefault (parid, fileref)
            par = par.parent

        comment = ''
        if media != None:
            for text in pulse.utils.xmliter (media):
                if text.type == 'element' and text.name == 'textobject':
                    for phrase in pulse.utils.xmliter (text):
                        if phrase.type == 'element' and phrase.name == 'phrase':
                            comment = phrase.getContent()

        if is_screenshot:
            doc.data['screens'].setdefault (None, fileref)

        doc.data['figures'][fileref] = {'comment': comment}

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)


def process_docbook_pofile (pofile, doc, **kw):
    lang = os.path.basename(pofile)[:-3]
    if not hasattr (doc, 'figures_by_lang'):
        doc.figures_by_lang = {}
    doc.figures_by_lang[lang] = []
    for ref in doc.data.get ('figures', {}).keys():
        dref = os.path.join (os.path.dirname (pofile), ref)
        if os.path.exists (dref):
            doc.figures_by_lang[lang].append (ref)
   
    rel_scm = pulse.utils.relative_path (pofile, pulse.config.scm_dir)
    if not os.path.exists (pofile):
        pulse.utils.warn ('No such file %s' % rel_scm)
        return
    mtime = os.stat(pofile).st_mtime
    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    po = pulse.parsers.Po (pofile)
    if doc.name.has_key('C') and po.has_message (doc.name['C']):
        doc.update (name={lang : po.get_translations (doc.name['C'])[0]})
    if doc.desc.has_key('C') and po.has_message (doc.desc['C']):
        doc.update (desc={lang : po.get_translations (doc.desc['C'])[0]})

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)


def process_credits (doc, **kw):
    if not hasattr (doc, 'credits'):
        return
    rels = []
    for cr_name, cr_email, cr_type, cr_maint in doc.credits:
        ent = None
        if cr_email != None:
            ent = pulse.db.Entity.get_or_create_email (cr_email)
        if ent == None:
            ident = u'/ghost/' + urllib.quote (cr_name)
            ent = pulse.db.Entity.get_or_create (ident, u'Ghost')
            if ent.ident == ident:
                ent.update (name=cr_name)
        if cr_name is not None:
            ent.extend (name=cr_name)
        if cr_email is not None:
            ent.extend (email=cr_email)
        rel = pulse.db.DocumentEntity.set_related (doc, ent)
        if cr_type in ('author', 'corpauthor'):
            rel.author = True
        elif cr_type == 'editor':
            rel.editor = True
        elif cr_type == 'publisher':
            rel.publisher = True
        if cr_maint:
            rel.maintainer = True
        rels.append (rel)
    doc.set_relations (pulse.db.DocumentEntity, rels)


def process_figures (doc, checkout, **kw):
    figures = doc.data.get ('figures', {}).keys()
    figures_by_lang = getattr (doc, 'figures_by_lang', {})
    figures_by_lang['C'] = figures
    ofs = list(pulse.db.OutputFile.select (type=u'figures', ident=doc.ident))
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
    missing = []
    for ref in figs:
        of = ofs_by_source.pop (ref, None)
        if of == None:
            infile = os.path.join (indir, ref)
            of = pulse.db.OutputFile (type=u'figures', ident=doc.ident, subdir=lang,
                                      filename=os.path.basename (ref), source=ref,
                                      datetime=datetime.datetime.utcnow())
            copy_image (infile, of)
        else:
            infile = os.path.join (indir, of.source)
            if kw.get('timestamps', True):
                try:
                    mtime = os.stat(infile).st_mtime
                    if mtime > time.mktime(of.datetime.timetuple()):
                        copy_image (infile, of)
                except:
                    missing.append (ref)
            else:
                copy_image (infile, of)
        if ref == screen:
            doc.data.setdefault ('screenshot', {})
            doc.data['screenshot'][lang] = of.id
    if len(missing) > 0:
        doc.error = u'Missing figures: ' + u', '.join (missing)
    for of in ofs_by_source.values():
        pulse.utils.log ('Deleting figure %s/%s' % (of.subdir, of.filename))
        try:
            os.remove (of.get_file_path())
            os.remove (of.get_file_path('thumbs'))
        except:
            pass
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
    of.datetime = datetime.datetime.utcnow()
    of.data['width'] = w
    of.data['height'] = h
    of.data['thumb_width'] = tw
    of.data['thumb_height'] = th


################################################################################
## XML Utilities

def normalize (s):
    if s == None:
        return s
    return re.sub('\s+', ' ', s).strip()

def personname (node):
    name = [None, None, None, None, None]
    namestr = None
    email = None
    for child in pulse.utils.xmliter (node):
        if child.type != 'element':
            continue
        if child.name == 'personname':
            namestr = personname(child)[0]
        elif child.name == 'email':
            email = child.getContent()
        elif namestr == None:
            try:
                i = ['honorific', 'firstname', 'othername', 'surname', 'lineage'].index(child.name)
                if name[i] == None:
                    name[i] = child.getContent()
            except ValueError:
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
        ident = None
    else:
        ident = pulse.utils.utf8dec (argv[0])

    if ident == None:
        docs = pulse.db.Branch.select (type=u'Document')
    elif ident.startswith ('/mod/'):
        docs = pulse.db.Branch.select (pulse.db.Branch.type == u'Document',
                                       pulse.db.Branch.parent_ident.like (ident))
    elif ident.startswith ('/set/'):
        docs = pulse.db.Branch.select (pulse.db.Branch.type == u'Document',
                                       pulse.db.Branch.parent_ident == pulse.db.SetModule.pred_ident,
                                       pulse.db.SetModule.subj_ident.like (ident))
    else:
        docs = pulse.db.Branch.select (pulse.db.Branch.type == u'Document',
                                       pulse.db.Branch.ident.like (ident))

    for doc in list(docs):
        try:
            update_document (doc, update=update, timestamps=timestamps)
            pulse.db.flush ()
        except:
            pulse.db.rollback ()
            raise
        else:
            pulse.db.commit ()

    return 0
