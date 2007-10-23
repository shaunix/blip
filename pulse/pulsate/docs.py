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

import os
import re
import xml.dom.minidom

import pulse.db
import pulse.scm
import pulse.parsers
import pulse.utils

synop = 'update information about documentation'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only documents with a matching identifier will be updated.'

checkouts = {}
def get_checkout (branch, update=True):
    if not checkouts.has_key (branch.ident):
        checkouts[branch.ident] = pulse.scm.Checkout.from_record (branch, update=update)
    return checkouts[branch.ident]

def update_gdu_docbook (doc, update=True, timestamps=True):
    checkout = get_checkout (doc.parent, update=update)
    name = {}
    desc = {}
    data = {}

    docfile = os.path.join (checkout.directory, doc.scm_dir, doc.scm_file)
    process_gdu_docbook_docfile (docfile, name, desc, data, timestamps=timestamps)

    if not name.has_key ('C') and doc.name.has_key ('C'):
        name['C'] = doc.name['C']
    if not desc.has_key ('C') and doc.desc.has_key ('C'):
        desc['C'] = doc.desc['C']

    author_rels = []
    editor_rels = []
    credit_rels = []
    maint_rels = []
    for cr_name, cr_email, cr_type, cr_maint in data.pop ('credits'):
        ent = None
        if cr_email != None:
            ent = pulse.db.Entity.selectBy (email=cr_email)
            if ent.count() > 0:
                ent = ent[0]
            else:
                ent = None
        if ent == None:
            ident = '/ghost/' + re.sub ('[^A-Za-z0-9]', '', cr_name)
            ent = pulse.db.Entity.get_record (ident=ident, type='Ghost')
            ent.update_name ({'C' : cr_name})
            if cr_email != None:
                ent.email = cr_email
        if cr_type in ('author', 'corpauthor'):
            author_rels.append (pulse.db.BranchEntityRelation.set_related (subj=doc,
                                                                           verb='DocumentAuthor',
                                                                           pred=ent))
        elif cr_type == 'editor':
            editor_rels.append (pulse.db.BranchEntityRelation.set_related (subj=doc,
                                                                           verb='DocumentEditor',
                                                                           pred=ent))
        else:
            credit_rels.append (pulse.db.BranchEntityRelation.set_related (subj=doc,
                                                                           verb='DocumentCredit',
                                                                           pred=ent))
        if cr_maint:
            maint_rels.append (pulse.db.BranchEntityRelation.set_related (subj=doc,
                                                                          verb='DocumentMaintainer',
                                                                          pred=ent))
    doc.set_relations (pulse.db.BranchEntityRelation, 'DocumentAuthor', author_rels)
    doc.set_relations (pulse.db.BranchEntityRelation, 'DocumentEditor', editor_rels)
    doc.set_relations (pulse.db.BranchEntityRelation, 'DocumentCredit', credit_rels)
    doc.set_relations (pulse.db.BranchEntityRelation, 'DocumentMaintainer', maint_rels)

    doc.update_name (name)
    doc.update_desc (desc)

def process_gdu_docbook_docfile (docfile, name, desc, data, **kw):
    rel_scm = pulse.utils.relative_path (docfile, pulse.config.scmdir)
    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        mtime = os.stat(docfile).st_mtime
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    title = None
    abstract = None
    credits = []
    dom = xml.dom.minidom.parse (docfile)
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

    #pulse.db.Timestamp.set_timestamp (rel_scm, mtime)


def update_gtk_doc (doc, update=True, timestamps=True):
    pass


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
    return re.sub('\s+', ' ', s).strip()

def personname (node):
    name = [None, None, None, None, None]
    namestr = None
    email = None
    for child in node.childNodes:
        if child.nodeType != child.ELEMENT_NODE:
            continue
        if child.tagName == 'personname':
            namestr = personname (child)
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
    return (namestr, email)


################################################################################
## main

def main (argv, options={}):
    update = not options.get ('--no-update', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix != None:
        docs = pulse.db.Branch.select ((pulse.db.Branch.q.type == 'Document') &
                                       (pulse.db.Branch.q.ident.startswith (prefix)) )
    else:
        docs = pulse.db.Branch.selectBy (type='Document')

    for doc in docs:
        if doc.subtype == 'gdu-docbook':
            update_gdu_docbook (doc, update=update, timestamps=timestamps)
        elif doc.subtype == 'gtk-doc':
            update_gtk_doc (doc, update=update, timestamps=timestamps)
        else:
            pulse.utils.log ('Skipping document %s with unknown type %s' % (doc.ident, doc.subtype))
