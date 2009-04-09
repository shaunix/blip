# Copyright (c) 2006-2009  Shaun McCance  <shaunm@gnome.org>
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

"""
ModuleScanner plugin for gnome-doc-utils documents.
"""

import os

from pulse import db, parsers, utils

import pulse.pulsate.docs
import pulse.pulsate.i18n
import pulse.pulsate.modules

import pulse.plugins.docbook

class GnomeDocUtilsModuleHandler (object):
    """
    ModuleScanner plugin for gnome-doc-utils documents.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.gdu_docs = []

    def process_file (self, dirname, basename, **kw):
        """
        Process a Makefile for gnome-doc-utils information.
        """
        is_gdu_doc = False
        if basename == 'Makefile.am':
            filename = os.path.join (dirname, basename)
            makefile = self.scanner.get_parsed_file (parsers.Automake, filename)
            for line in makefile.get_lines():
                if line.startswith ('include $(top_srcdir)/'):
                    if line.endswith ('gnome-doc-utils.make'):
                        is_gdu_doc = True
                        break
        if not is_gdu_doc:
            return

        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        doc_module = makefile['DOC_MODULE']
        if doc_module == '@PACKAGE_NAME@':
            doc_module = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
        ident = u'/'.join(['/doc', bserver, bmodule, doc_module, bbranch])
        document = db.Branch.get_or_create (ident, u'Document')
        document.parent = branch

        relpath = utils.relative_path (dirname, checkout.directory)

        data = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            data[key] = getattr(branch, key)
        data['subtype'] = u'gdu-docbook'
        data['scm_dir'] = os.path.join (relpath, 'C')
        data['scm_file'] = doc_module + '.xml'
        document.update (data)

        translations = []
        if makefile.has_key ('DOC_LINGUAS'):
            for lang in makefile['DOC_LINGUAS'].split():
                lident = u'/l10n/' + lang + document.ident
                translation = db.Branch.get_or_create (lident, u'Translation')
                translations.append (translation)
                ldata = {}
                for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                    ldata[key] = data[key]
                ldata['subtype'] = u'xml2po'
                ldata['scm_dir'] = os.path.join (
                    utils.relative_path (dirname, checkout.directory),
                    lang)
                ldata['scm_file'] = lang + '.po'
                translation.parent = document
                translation.update (ldata)
            document.set_children (u'Translation', translations)

        if not kw.get('no_docs', False):
            pulse.pulsate.docs.update_document (document, checkout=checkout, **kw)

        if not kw.get('no_i18n', False):
            for po in translations:
                pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

        if document is not None:
            self.scanner.add_child (document)

pulse.pulsate.modules.ModuleScanner.register_plugin (GnomeDocUtilsModuleHandler)


class GnomeDocUtilsDocumentHandler (object):
    """
    DocumentScanner plugin for gnome-doc-utils documents.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def update_document (self, **kw):
        document = self.scanner.document
        checkout = self.scanner.checkout
        if document.subtype != 'gdu-docbook':
            return False

        document.icon_name = document.parent.icon_name
        document.icon_dir = document.parent.icon_dir

        docbook = pulse.plugins.docbook.DocBookHandler (self)

        docfile = os.path.join (checkout.directory, document.scm_dir, document.scm_file)
        docbook.process_docfile (docfile, **kw)

        docbook.process_translations (**kw)
        docbook.process_credits (**kw)
        docbook.process_figures (**kw)

        makedir = os.path.join (checkout.directory, os.path.dirname (document.scm_dir))
        makefile = pulse.parsers.Automake (os.path.join (makedir, 'Makefile.am'))
        xmlfiles = []
        doc_module = makefile['DOC_MODULE']
        if doc_module == '@PACKAGE_NAME@':
            doc_module = document.parent.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
        fnames = ([doc_module + '.xml']  +
                  makefile.get('DOC_INCLUDES', '').split() +
                  makefile.get('DOC_ENTITIES', '').split() )
        for fname in (fnames):
            xmlfiles.append (fname)

        document.data['xmlfiles'] = sorted (xmlfiles)

        files = [os.path.join (document.scm_dir, f) for f in xmlfiles]
        revision = pulse.db.Revision.get_last_revision (branch=document.parent, files=files)
        if revision != None:
            document.mod_datetime = revision.datetime
            document.mod_person = revision.person

        files = [os.path.join (document.scm_dir, f) for f in document.data.get ('xmlfiles', [])]
        if len(files) == 0:
            document.mod_score = 0
        else:
            pulse.pulsate.update_graphs (document,
                                         {'branch' : document.parent, 'files' : files},
                                         10, **kw)
        return True


pulse.pulsate.docs.DocumentScanner.register_plugin (GnomeDocUtilsDocumentHandler)
