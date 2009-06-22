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
Plugins for the Evolution Quick Reference Card.
"""
import os

from rdflib.Graph import Graph

import pulse.pulsate.modules


class BugHandler(object):
    def __init__ (self, scanner):
        self.scanner = scanner

    def process_file (self, dirname, basename, **kw):
        if not basename.endswith('.doap'):
            return

        store = Graph()
        g = store.parse(os.path.join(dirname, basename))
        query = """
        PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
        PREFIX doap: <http://usefulinc.com/ns/doap#>

        SELECT $bug
        WHERE {
              $project rdf:type doap:Project .
              $project doap:bug-database $bug
        }"""

        results = list(g.query(query))
        if len(results) == 1:
            self.scanner.branch.bug_database =  unicode(results[0][0])

pulse.pulsate.modules.ModuleScanner.register_plugin (BugHandler)
