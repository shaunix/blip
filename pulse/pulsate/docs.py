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
import math
import os
import os.path
import re
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
args['no-history'] = (None, 'do not check SCM history')
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


def update_gdu_docbook (doc, **kw):
    checkout = get_checkout (doc, update=kw.get('update', True))
    name = {}
    desc = {}
    data = {}

    # FIXME: we want to add "audience" for docs.  use that here
    cnt = db.Branch.objects.filter (type='Document',
                                    subtype__startswith='gdu-',
                                    parent=doc.parent)
    if cnt.count() == 1:
        data['icon_name'] = doc.parent.icon_name
        data['icon_dir'] = doc.parent.icon_dir

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_docbook_docfile (docfile, name, desc, data, timestamps=kw.get('timestamps', True))

    if data.has_key ('credits'):
        set_credits (doc, data.pop ('credits'))

    if not name.has_key ('C') and doc.name.has_key ('C'):
        name['C'] = doc.name['C']
    if not desc.has_key ('C') and doc.desc.has_key ('C'):
        desc['C'] = doc.desc['C']

    translations = db.Branch.objects.filter (type='Translation', parent=doc)
    for translation in translations:
        pofile = os.path.join (checkout.directory, translation.scm_dir, translation.scm_file)
        process_docbook_pofile (pofile, name, desc, data, timestamps=kw.get('timestamps', True))

    makedir = os.path.join (checkout.directory, os.path.dirname (doc.scm_dir))
    makefile = pulse.parsers.Automake (os.path.join (makedir, 'Makefile.am'))
    xmlfiles = []
    fnames = ([makefile['DOC_MODULE']+'.xml']  +
              makefile.get('DOC_INCLUDES', '').split() +
              makefile.get('DOC_ENTITIES', '').split() )
    if kw.get('history', True):
        pulse.utils.log ('Checking history for %i files for %s' % (len(fnames), doc.ident))
    for fname in (fnames):
        xmlfiles.append (fname)
        if kw.get('history', True):
            fullname = os.path.join (makedir, 'C', fname)
            rel_ch = pulse.utils.relative_path (fullname, checkout.directory)
            since = db.Revision.get_last_revision (doc, fname)
            if since != None:
                since = since.revision
            serverid = '.'.join (pulse.scm.server_name (checkout.scm_type, checkout.scm_server).split('.')[-2:])
            for hist in checkout.get_file_history (rel_ch, since=since):
                pident = '/person/' + serverid + '/' + hist['userid']
                pers = db.Entity.get_record (pident, 'Person')
                rev = db.Revision (branch=doc, person=pers, filename=fname, filetype='xml',
                                   revision=hist['revision'], datetime=hist['date'], comment=hist['comment'])
                rev.save()
    revision = db.Revision.get_last_revision (doc, False)
    if revision != None:
        data['mod_datetime'] = revision.datetime
        data['mod_person'] = revision.person

    pulse.utils.log ('Creating commit graph for %s' % doc.ident)
    now = datetime.datetime.now()
    threshhold = now - datetime.timedelta(days=168)
    stats = [0] * 24
    revs = db.Revision.select_revisions (branch=doc, since=threshhold)
    for rev in list(revs):
        idx = (now - rev.datetime).days
        idx = 23 - (idx // 7)
        if idx < 24: stats[idx] += 1
    score = 0;
    for i in range(len(stats)):
        score += (math.sqrt(i + 1) / 5) * stats[i]
    data['mod_score'] = int(score)
    graphdir = os.path.join (*([pulse.config.web_graphs_dir] + doc.ident.split('/')[1:]))
    if not os.path.exists (graphdir):
        os.makedirs (graphdir)
    graph = pulse.graphs.BarGraph (stats, 10)
    graph.save (os.path.join (graphdir, 'commits.png'))
    graph.save_data (os.path.join (graphdir, 'commits.imap'))

    xmlfiles = sorted(xmlfiles)
    if doc.data.get('xmlfiles') != xmlfiles:
        data['xmlfiles'] = xmlfiles

    doc.update (data, name=name, desc=desc)
    doc.save()


def update_gtk_doc (doc, **kw):
    checkout = get_checkout (doc, update=kw.get('update', True))
    name = {}
    desc = {}
    data = {}

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_docbook_docfile (docfile, name, desc, data, timestamps=kw.get('timestamps', True))

    if data.has_key ('credits'):
        set_credits (doc, data.pop ('credits'))

    if not name.has_key ('C') and doc.name.has_key ('C'):
        name['C'] = doc.name['C']
    if not desc.has_key ('C') and doc.desc.has_key ('C'):
        desc['C'] = doc.desc['C']

    doc.update (data, name=name, desc=desc)
    doc.save()


def process_docbook_docfile (docfile, name, desc, data, **kw):
    rel_scm = pulse.utils.relative_path (docfile, pulse.config.scm_dir)
    if not os.path.exists (docfile):
        pulse.utils.warn ('No such file %s' % rel_scm)
        return
    mtime = os.stat(docfile).st_mtime
    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.warn ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    title = None
    abstract = None
    credits = []
    try:
        dom = xml.dom.minidom.parse (docfile)
    except:
        pulse.utils.warn ('Failed to load file %s' % rel_scm)
        return
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
        name['C'] = normalize (title)
    if abstract != None:
        desc['C'] = normalize (abstract)
    data['credits'] = credits

    db.Timestamp.set_timestamp (rel_scm, mtime)


def process_docbook_pofile (pofile, name, desc, data, **kw):
    rel_scm = pulse.utils.relative_path (pofile, pulse.config.scm_dir)
    if not os.path.exists (pofile):
        pulse.utils.log ('No such file %s' % rel_scm)
        return
    mtime = os.stat(pofile).st_mtime
    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    lang = os.path.basename(pofile)[:-3]
    po = pulse.parsers.Po (pofile)
    if name.has_key('C') and po.has_message (name['C']):
        name[lang] = po.get_message_str (name['C'])
    if desc.has_key('C') and po.has_message (desc['C']):
        desc[lang] = po.get_message_str (desc['C'])
   
    db.Timestamp.set_timestamp (rel_scm, mtime)


def update_scm_file (doc, filename):
    print filename
    pass


def set_credits (doc, credits):
    rels = []
    for cr_name, cr_email, cr_type, cr_maint in credits:
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
    history = not options.get ('--no-history', False)
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
        if doc.subtype == 'gdu-docbook':
            update_gdu_docbook (doc, update=update, timestamps=timestamps, history=history)
        elif doc.subtype == 'gtk-doc':
            update_gtk_doc (doc, update=update, timestamps=timestamps, history=history)
        else:
            pulse.utils.log ('Skipping document %s with unknown type %s' % (doc.ident, doc.subtype))
