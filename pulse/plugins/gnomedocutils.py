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

import pulse.pulsate.i18n
import pulse.pulsate.modules

class GnomeDocUtilsHandler (object):
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
        if basename == 'Makefile.am':
            makefile = self.scanner.get_parsed_file (parsers.Automake,
                                                     os.path.join (dirname, basename))
            for line in makefile.get_lines():
                if line.startswith ('include $(top_srcdir)/'):
                    if line.endswith ('gnome-doc-utils.make'):
                        self.gdu_docs.append((dirname, makefile))
                        break

    def update (self, **kw):
        """
        Update all gnome-doc-utils documents for a module.
        """
        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]
        for docdir, makefile in self.gdu_docs:
            doc_module = makefile['DOC_MODULE']
            if doc_module == '@PACKAGE_NAME@':
                doc_module = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
            ident = u'/'.join(['/doc', bserver, bmodule, doc_module, bbranch])
            document = db.Branch.get_or_create (ident, u'Document')
            document.parent = branch

            relpath = utils.relative_path (docdir, checkout.directory)

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
                        utils.relative_path (docdir, checkout.directory),
                        lang)
                    ldata['scm_file'] = lang + '.po'
                    translation.update (ldata)
                document.set_children (u'Translation', translations)

            if not kw.get('no_i18n', False):
                for po in translations:
                    pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

            if document is not None:
                self.scanner.add_child (document)

pulse.pulsate.modules.ModuleScanner.register_plugin (GnomeDocUtilsHandler)
