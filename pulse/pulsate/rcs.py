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
import os
import re
import sys
import xml.dom.minidom

from sqlobject.sqlbuilder import LIKE

import pulse.db as db
import pulse.po as po
import pulse.rcs as rcs
import pulse.utils as utils

synop = 'update documentation information from version control'
def usage (fd=sys.stderr):
    print >>fd, ('Usage: %s docs' % sys.argv[0])

# FIXME: move to a dedicated Makefile.am parser module
def read_var (line, fd):
    txt = line.strip()
    txt = txt[txt.find('=') + 1: ]
    if txt.endswith ('\\'):
        txt = txt[:-1]
        while True:
            line = fd.readline()
            if line == None:
                break
            txt += line.strip()
            if txt.endswith ('\\'):
                txt = txt[:-1]
            else:
                break
    return txt.strip()

# FIXME: move to a dedicated xml utils module?
def string_value (node):
    if node.nodeType == node.ELEMENT_NODE:
        str = u''
        for child in node.childNodes:
            str += string_value (child)
        return str
    elif node.nodeType == node.TEXT_NODE:
        return node.nodeValue
    else:
        return u''

def update_branch (branch, update=True, done=set()):
    bident = branch.ident
    if bident in done:
        co = rcs.Checkout (branch, update=False)
    else:
        co = rcs.Checkout (branch, update=update)
        done.add (bident)

    for dir in os.walk (co.directory):
        if 'Makefile.am' in dir[2]:
            makefile = os.path.join (dir[0], 'Makefile.am')

            gdu_doc = False
            gtk_doc = False

            fd = file (makefile)
            line = fd.readline()
            while line:
                if line.startswith ('include $(top_srcdir)/gnome-doc-utils.make'):
                    gdu_doc = True
                if gdu_doc:
                    if re.match('''DOC_LINGUAS\s*=''', line):
                        linguas = read_var (line, fd)
                        translations = linguas.strip().split()
                    if re.match('''DOC_MODULE\s*=''', line):
                        docfile = read_var (line, fd)
                line = fd.readline()
            fd.close()

            if gdu_doc:
                dident = ('docs/%s/%s/' % tuple(bident.split('/')[1:])) + docfile
                doc = db.Document.select (db.Document.q.ident == dident)
                if doc.count() > 0:
                    doc = doc[0]
                else:
                    rcs_dir = dir[0][len(co.directory):].strip('/')
                    utils.log ('Creating document %s' % dident)
                    doc = db.Document (ident = dident,
                                       tool = 'gnome-doc-utils',
                                       branch = branch,
                                       rcs_server = branch.rcs_server,
                                       rcs_module = branch.rcs_module,
                                       rcs_branch = branch.rcs_branch,
                                       rcs_dir = rcs_dir,
                                       bug_server = branch.bug_server,
                                       bug_product = branch.bug_product)
                update_document (doc, docfile)
                for lang in translations:
                    update_doc_translation (doc, lang)
        if 'POTFILES.in' in dir[2]:
            potfile = os.path.join (dir[0], 'POTFILES.in')
            print potfile
    # end for dir

def update_document (doc, docfile):
    co = rcs.Checkout (doc, update=False)

    utils.log ('Updating document %s' % doc.ident)
    doc.updated = datetime.datetime.now()

    if doc.tool == 'gnome-doc-utils':
        docpath = os.path.join (co.directory, 'C', docfile + '.xml')
        if not os.access (docpath, os.F_OK):
            doc.error = ('The file "%s" does not exist.' % docfile)
            return

        dom = xml.dom.minidom.parse (docpath)
        for root in dom.childNodes:
            if root.nodeType == root.ELEMENT_NODE:
                break
        info = None
        title = None
        for child in root.childNodes:
            if child.nodeName in ['articleinfo', 'bookinfo']:
                info = child
            elif child.nodeName == 'title':
                title = child
        if title == None:
            for child in info.childNodes:
                if child.nodeName == 'title':
                    title = child
        if title != None:
            doc.set_text ('name', 'C', string_value (title))
        
        doc.error = None

# FIXME: make the signature like the other update funcs
def update_doc_translation (doc, lang):
    ident = 'l10n/' + lang + ('/%s/%s/docs/%s' % tuple(doc.ident.split('/')[1:4]))

    rec = db.Translation.select (db.Translation.q.ident == ident)
    if rec.count() > 0:
        rec = rec[0]
    else:
        rec = db.Translation (ident = ident,
                              source = doc,
                              tool = 'xml2po',
                              rcs_server = doc.rcs_server,
                              rcs_module = doc.rcs_module,
                              rcs_branch = doc.rcs_branch,
                              rcs_dir = os.path.join (doc.rcs_dir, lang),
                              rcs_file = lang + '.po')
    co = rcs.Checkout (rec)
    podict = po.PoFile (co.file)
    title = podict[doc.get_text('name', ['C'])]
    if title != None:
        doc.set_text ('name', lang, title['msgstr'])


def main (argv):
    update = True
    like = None
    if len (argv) > 2:
        for arg in argv[2:]:
            if arg.startswith ('-'):
                if arg == '--no-update':
                    update = False
            else:
                like = arg

    if like != None:
        branches = db.Branch.select (LIKE (db.Branch.q.ident, ('%%%s%%' % like)))
    else:
        branches = db.Branch.select ()

    for branch in branches:
        update_branch (branch, update=update)
    return 0
