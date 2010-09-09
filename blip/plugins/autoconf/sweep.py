# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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
ModuleScanner plugin for module configuration files.
"""

import commands
import os

import blinq.config

import blip.db
import blip.utils
import blip.plugins.modules.sweep

import blip.parsers
import blip.parsers.autoconf

class AutoconfHandler (blip.plugins.modules.sweep.ModuleFileScanner):
    """
    ModuleScanner plugin for module configuration files.
    """

    def process_file (self, dirname, basename):
        """
        Process a configure.in or configure.ac file.
        """
        if dirname != self.scanner.repository.directory:
            return
        if basename not in ('configure.in', 'configure.ac'):
            return

        filename = os.path.join (dirname, basename)
        with blip.db.Timestamp.stamped (filename, self.scanner.repository) as stamp:
            stamp.check (self.scanner.request.get_tool_option ('timestamps'))
            stamp.log ()

            autoconf = blip.parsers.get_parsed_file (blip.parsers.autoconf.Autoconf,
                                                     filename)

            version = autoconf.get_package_version ()
            series = version.split('.')[:2]
            try:
                minor = int (series[1])
                if minor % 2 == 1:
                    minor += 1
                series[1] = str (minor)
            except:
                pass
            series = '.'.join (series)

            self.scanner.branch.data['pkgname'] = autoconf.get_package_name ()
            self.scanner.branch.data['pkgversion'] = version
            self.scanner.branch.data['pkgseries'] = series
