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
Plugins for gtk-doc documents.
"""

import os

from pulse import db, parsers, utils

import pulse.pulsate.docs
import pulse.pulsate.modules

class GtkDocModuleHandler (object):
    """
    ModuleScanner plugin for gtk-doc documents.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.gtk_docs = []

    def process_file (self, dirname, basename, **kw):
        """
        Process a Makefile for gtk-doc information.
        """
        is_gtk_doc = False
        if basename == 'Makefile.am':
            filename = os.path.join (dirname, basename)
            makefile = self.scanner.get_parsed_file (parsers.Automake, filename)
            for line in makefile.get_lines():
                if line.startswith ('include $(top_srcdir)/'):
                    if line.endswith ('gtk-doc.make'):
                        is_gtk_doc = True
                        break
        if not is_gtk_doc:
            return

        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        doc_module = makefile['DOC_MODULE']
        ident = u'/'.join(['/ref', bserver, bmodule, doc_module, bbranch])
        document = db.Branch.get_or_create (ident, u'Document')
        relpath = utils.relative_path (dirname, checkout.directory)

        data = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            data[key] = getattr(branch, key)
        data['subtype'] = u'gtk-doc'
        data['scm_dir'] = relpath
        scm_file = makefile['DOC_MAIN_SGML_FILE']
        if '$(DOC_MODULE)' in scm_file:
            scm_file = scm_file.replace ('$(DOC_MODULE)', doc_module)
        data['scm_file'] = scm_file

        document.update (data)

        if not kw.get('no_docs', False):
            pulse.pulsate.docs.update_document (document, checkout=checkout, **kw)

        if document is not None:
            self.scanner.add_child (document)

pulse.pulsate.modules.ModuleScanner.register_plugin (GtkDocModuleHandler)


class GtkDocDocumentHandler (object):
    """
    DocumentScanner plugin for gtk-doc documents.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def update_document (self, **kw):
        document = self.scanner.document
        checkout = self.scanner.checkout
        if document.subtype != 'gtk-doc':
            return False

        docbook = pulse.plugins.docbook.DocBookHandler (self)

        docfile = os.path.join (checkout.directory, document.scm_dir, document.scm_file)
        docbook.process_docfile (docfile, **kw)

        docbook.process_credits (**kw)
        docbook.process_figures (**kw)

        return True

pulse.pulsate.docs.DocumentScanner.register_plugin (GtkDocDocumentHandler)
