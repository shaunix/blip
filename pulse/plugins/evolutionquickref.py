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
ModuleScanner plugin for the Evolution Quick Reference Card.
"""

import os
import re

from pulse import db, parsers, utils

import pulse.pulsate.i18n
import pulse.pulsate.modules

class EvolutionQuickRefHandler (object):
    """
    ModuleScanner plugin for the Evolution Quick Reference Card.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def process_file (self, dirname, basename, **kw):
        """
        Process a Makefile.am file for the Evolution Quick Reference Card.
        """
        branch = self.scanner.branch
        checkout = self.scanner.checkout
        is_quickref = False
        if branch.scm_server == 'http://svn.gnome.org/svn/' and branch.scm_module == 'evolution':
            if basename == 'Makefile.am':
                if os.path.join (checkout.directory, 'help/quickref') == dirname:
                    is_quickref = True
        if not is_quickref:
            return

        filename = os.path.join (dirname, basename)
        makefile = self.scanner.get_parsed_file (parsers.Automake, filename)

        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        ident = u'/'.join(['/doc', bserver, bmodule, u'quickref', bbranch])
        document = db.Branch.get_or_create (ident, u'Document')
        document.parent = branch

        relpath = utils.relative_path (dirname, checkout.directory)

        data = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            data[key] = getattr(branch, key)
        data['subtype'] = u'evolution-quickref'
        data['scm_dir'] = os.path.join (relpath, 'C')
        data['scm_file'] = u'quickref.tex'
        document.update (data)

        texfile = os.path.join (dirname, 'C', 'quickref.tex')
        title = get_quickref_title (texfile)
        if title is not None:
            document.update (name=title)

        langs = makefile['SUBDIRS'].split ()
        translations = []
        for lang in langs:
            lident = u'/l10n/' + lang + document.ident
            translation = db.Branch.get_or_create (lident, u'Translation')
            translations.append (translation)
            ldata = {}
            for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                ldata[key] = data[key]
            ldata['subtype'] = u'evolution-quickref'
            ldata['scm_dir'] = os.path.join (
                utils.relative_path (dirname, checkout.directory),
                lang)
            ldata['scm_file'] = u'quickref.tex'
            translation.parent = document
            translation.update (ldata)
        document.set_children (u'Translation', translations)

        if not kw.get('no_i18n', False):
            for po in translations:
                pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

        if not kw.get('no_docs', False):
            pulse.pulsate.docs.update_document (document, checkout=checkout, **kw)

        if document is not None:
            self.scanner.add_child (document)

def get_quickref_title (filename):
    regexp = re.compile ('\\s*\\\\textbf{\\\\Huge{(.*)}}')
    for line in open (filename):
        match = regexp.match (line)
        if match:
            return match.group(1)
    return None

pulse.pulsate.modules.ModuleScanner.register_plugin (EvolutionQuickRefHandler)
