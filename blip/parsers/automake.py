# Copyright (c) 2007-2010  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

"""Various useful parsers of varying quality."""

import re

import blinq.utils

class Automake (object):
    """
    Parse a Makefile.am file.

    This class parses a Makefile.am file, allowing you to extract information
    from them.  Directives for make are ignored.  This is only useful for
    extracting variables.
    """

    def __init__ (self, filename):
        self._variables = {}
        self._lines = []
        regexp = re.compile ('''([A-Za-z_]+)(\s*=)(.*)''')
        fd = open (filename)
        line = fd.readline ()
        while line:
            line = blinq.utils.utf8dec (line)
            if '#' in line:
                line = line[line.index('#')]
            match = regexp.match (line)
            if match:
                varname = match.group(1)
                vartxt = match.group(3).strip()
                if vartxt.endswith ('\\'):
                    vartxt = vartxt[:-1]
                    line = fd.readline ()
                    while line:
                        if '#' in line:
                            line = line[line.index('#')]
                        vartxt += line.strip()
                        if vartxt.endswith ('\\'):
                            vartxt = vartxt[:-1]
                        else:
                            break
                        line = fd.readline()
                self._variables[varname] = vartxt
                self._lines.append (match.group(1) + match.group(2) + vartxt)
            else:
                self._lines.append (line.strip())

            if line:
                line = fd.readline ()

    def get_lines (self):
        """Get the canonicalized lines from the automake file."""
        return self._lines

    def __getitem__ (self, key):
        """Get the value of an automake variable."""
        return self._variables[key]

    def __contains__ (self, key):
        """Allow 'x in Automake' checks"""
        return key in self._variables

    def get (self, key, val=None):
        """Get the value of an automake variable, or return a default."""
        return self._variables.get(key, val)

    def has_key (self, key):
        """Check if the variable is set in the automake file."""
        return self._variables.has_key (key)
