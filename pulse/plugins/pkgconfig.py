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
ModuleScanner plugin for pkgconfig files.
"""

import os
import re

from pulse import config, db, utils

import pulse.pulsate.modules

class PkgConfigHandler (object):
    """
    ModuleScanner plugin for pkgconfig files.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.pkgconfigs = []
        self.libdocs = []

    def process_file (self, dirname, basename, **kw):
        """
        Process a file to determine whether it's a pkgconfig file.
        """
        if re.match ('.*\.pc(\.in)+$', basename):
            self.process_library (os.path.join (dirname, basename), **kw)

    def process_library (self, filename, **kw):
        """
        Process a library from a pkgconfig file.
        """
        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        basename = os.path.basename (filename)[:-6]
        rel_ch = utils.relative_path (filename, checkout.directory)
        rel_scm = utils.relative_path (filename, config.scm_dir)
        mtime = os.stat(filename).st_mtime
        # Hack for GTK+'s uninstalled pkgconfig files
        if '-uninstalled' in basename:
            return

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                data = {'parent' : branch}
                data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
                libs = db.Branch.select (type=u'Library', **data)
                try:
                    lib = libs.one ()
                    self.scanner.add_child (lib)
                    return
                except:
                    return
        utils.log ('Processing file %s' % rel_scm)

        libname = ''
        libdesc = ''
        for line in open (filename):
            if line.startswith ('Name:'):
                libname = line[5:].strip()
            elif line.startswith ('Description:'):
                libdesc = line[12:].strip()
        if libname == '':
            return

        ident = u'/'.join(['/lib', bserver, bmodule, basename, bbranch])
        lib = db.Branch.get_or_create (ident, u'Library')

        if libname == '@PACKAGE_NAME@':
            libname = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')

        lib.update (name=libname, desc=libdesc)

        docident = u'/'.join(['/ref', bserver, bmodule, basename, bbranch])
        self.libdocs.append ((lib, docident))

        data = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            data[key] = getattr(branch, key)
        data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)

        lib.update (data)

        db.Timestamp.set_timestamp (rel_scm, mtime)
        if lib is not None:
            self.scanner.add_child (lib)

    def update (self, **kw):
        """
        Update other information about libraries in a module.

        This function will locate documentation for a library.  This happens
        in the update phase to allow other plugins to add documents.
        """
        for lib, docident in self.libdocs:
            doc = db.Branch.get (docident)
            if doc is None:
                match = re.match ('(.+)-\\d+(\\d\\d+)?', basename)
                if match:
                    docident = u'/'.join(['/ref', bserver, bmodule, match.group(1), bbranch])
                    doc = db.Branch.get (docident)
            if doc is not None:
                rel = db.Documentation.set_related (lib, doc)
                lib.set_relations (db.Documentation, [rel])

pulse.pulsate.modules.ModuleScanner.register_plugin (PkgConfigHandler)
