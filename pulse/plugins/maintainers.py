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
ModuleScanner plugin for MAINTAINERS files.
"""

import os

from pulse import config, db, scm, utils

import pulse.pulsate.modules

class MaintainersHandler (object):
    """
    ModuleScanner plugin for MAINTAINERS files.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def process_file (self, dirname, basename, **kw):
        """
        Process a MAINTAINERS file.
        """
        is_maintainers = False
        if dirname == self.scanner.checkout.directory:
            if basename == 'MAINTAINERS':
                is_maintainers = True
        if not is_maintainers:
            return

        filename = os.path.join (dirname, basename)
        branch = self.scanner.branch
        rel_scm = utils.relative_path (filename, config.scm_dir)
        mtime = os.stat(filename).st_mtime

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            mtime = os.stat(filename).st_mtime
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                return
        utils.log ('Processing file %s' % rel_scm)

        start = True
        name = None
        email = None
        userid = None
        maints = []
        def add_maint ():
            if name != None and userid != None:
                maints.append ((name, userid, email))
        for line in open (filename):
            line = utils.utf8dec (line.rstrip())
            if line.startswith ('#'):
                continue
            if line == "":
                add_maint ()
                name = email = userid = None
                start = True
                continue

            if start:
                name = line
                start = False
            elif line.startswith ('E-mail:'):
                email = line[7:].strip()
            elif line.startswith ('Userid:'):
                userid = line[7:].strip()
        add_maint ()
        serverid = '.'.join (scm.server_name (branch.scm_type, branch.scm_server).split('.')[-2:])
        rels = []
        for name, userid, email in maints:
            ident = u'/person/%s@%s' % (userid, serverid)
            person = db.Entity.get_or_create (ident, u'Person')
            person.update (name=name)
            if email != None:
                person.email = email
            rel = db.ModuleEntity.set_related (branch, person, maintainer=True)
            rels.append (rel)
        branch.set_relations (db.ModuleEntity, rels)

        db.Timestamp.set_timestamp (rel_scm, mtime)

pulse.pulsate.modules.ModuleScanner.register_plugin (MaintainersHandler)
