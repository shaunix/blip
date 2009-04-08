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
ModuleScanner plugin for intltool-managed translation domains.
"""

import os

from pulse import config, db, utils

import pulse.pulsate.i18n
import pulse.pulsate.modules

class PotHandler (object):
    """
    ModuleScanner plugin for intltool-managed translation domains.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.podirs = []

    def process_file (self, dirname, basename, **kw):
        """
        Process a POTFILES.in file for intltool information.
        """
        if not basename == 'POTFILES.in':
            return

        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        ident = u'/'.join(['/i18n', bserver, bmodule, os.path.basename (dirname), bbranch])

        domain = db.Branch.get_or_create (ident, u'Domain')
        domain.parent = branch

        scmdata = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            scmdata[key] = getattr(branch, key)
        scmdata['scm_dir'] = utils.relative_path (dirname, checkout.directory)
        domain.update (scmdata)

        linguas = os.path.join (dirname, 'LINGUAS')
        if not os.path.isfile (linguas):
            domain.error = u'No LINGUAS file'
            return
        else:
            domain.error = None

        rel_scm = utils.relative_path (linguas, config.scm_dir)
        mtime = os.stat(linguas).st_mtime
        langs = []
        translations = []

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                return
        utils.log ('Processing file %s' % rel_scm)

        fd = open (linguas)
        for line in fd:
            if line.startswith ('#') or line == '\n':
                continue
            for lang in line.split():
                langs.append (lang)
        for lang in langs:
            lident = u'/l10n/' + lang + domain.ident
            translation = db.Branch.get_or_create (lident, u'Translation')
            translations.append (translation)
            ldata = {}
            for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                ldata[key] = scmdata[key]
            ldata['subtype'] = 'intltool'
            ldata['scm_dir'] = scmdata['scm_dir']
            ldata['scm_file'] = lang + '.po'
            translation.parent = domain
            translation.update (ldata)

        if not kw.get('no_i18n', False):
            for po in translations:
                pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

        db.Timestamp.set_timestamp (rel_scm, mtime)
        if domain is not None:
            self.scanner.add_child (domain)

pulse.pulsate.modules.ModuleScanner.register_plugin (PotHandler)
