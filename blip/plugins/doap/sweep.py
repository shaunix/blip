# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
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

import os
import urllib

import RDF

import blip.db
import blip.utils
import blip.plugins.modules.sweep

class DoapScanner (blip.plugins.modules.sweep.ModuleFileScanner):
    def process_file (self, dirname, basename):
        if (dirname == self.scanner.repository.directory
            and basename == self.scanner.branch.scm_module + '.doap'):

            filename = os.path.join (dirname, basename)
            with blip.db.Error.catch (self.scanner.branch, 'Invalid DOAP file'):
                with blip.db.Timestamp.stamped (filename, self.scanner.repository) as stamp:
                    stamp.check (self.scanner.request.get_tool_option ('timestamps'))
                    stamp.log ()

                    model = RDF.Model()
                    if not model.load ('file://' + urllib.pathname2url(filename)):
                        return
                    query = RDF.SPARQLQuery(' PREFIX doap: <http://usefulinc.com/ns/doap#>'
                                            ' SELECT ?name ?desc'
                                            ' WHERE {'
                                            '  ?project a doap:Project ;'
                                            '    doap:name ?name ;'
                                            '    doap:shortdesc ?desc .'
                                            ' FILTER('
                                            '  langMatches(lang(?name), "en") &&'
                                            '  langMatches(lang(?desc), "en")'
                                            ' )} LIMIT 1')
                    for defs in query.execute (model):
                        self.scanner.branch.update ({
                                'name': defs['name'].literal_value['string'],
                                'desc': defs['desc'].literal_value['string']
                                })
                        break
                    query = RDF.SPARQLQuery(' PREFIX doap: <http://usefulinc.com/ns/doap#>'
                                            ' PREFIX foaf: <http://xmlns.com/foaf/0.1/>'
                                            ' SELECT ?name ?mbox'
                                            ' WHERE {'
                                            '  ?project a doap:Project .'
                                            '  ?project doap:maintainer ?person .'
                                            '  ?person a foaf:Person ;'
                                            '    foaf:name ?name ;'
                                            '    foaf:mbox ?mbox .'
                                            ' }')
                    maints = []
                    print 'foo'
                    for defs in query.execute (model):
                        mbox = defs['mbox'].uri
                        if mbox is not None:
                            mbox = unicode (mbox)
                        if mbox.startswith ('mailto:'):
                            mbox = mbox[7:]
                            ent = blip.db.Entity.get_or_create_email (mbox)
                            maints.append (blip.db.ModuleEntity.set_related (self.scanner.branch,
                                                                             ent, maintainer=True))
                    self.scanner.branch.set_relations (blip.db.ModuleEntity, maints)

    def post_process (self):
        pass
