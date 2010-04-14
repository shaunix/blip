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

import blinq.config
import blinq.ext

import blip.data
import blip.db
import blip.scm
import blip.sweep


class SetSweeper (blinq.ext.ExtensionPoint):
    @classmethod
    def sweep_set (cls, record, data, request):
        return False


class SetsResponder (blip.sweep.SweepResponder):
    command = 'sets'
    synopsis = 'update information about sets and the modules they contain'

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--no-update',
                                 dest='update_scm',
                                 action='store_false',
                                 default=True,
                                 help='do not update SCM repositories')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)

        data = blip.data.Data (os.path.join (blinq.config.input_dir, 'sets.xml'))

        for key in data.data.keys():
            if data.data[key]['blip:type'] == 'set':
                cls.update_set (data.data[key], request)

        #if False:
        #    update_deps ()

        blip.db.commit ()
        return response

    @classmethod
    def update_set (cls, data, request, parent=None):
        ident = u'/set/' + data['blip:id']
        record = blip.db.ReleaseSet.get_or_create (ident, u'Set')
        if parent:
            record.parent = parent

        if data.has_key ('name'):
            record.update (name=data['name'])

        #if data.has_key ('links'):
        #    pulse.pulsate.update_links (record, data['links'])

        #if data.has_key ('schedule'):
        #    pulse.pulsate.update_schedule (record, data['schedule'])

        # Sets may contain either other sets or modules, not both
        if data.has_key ('set'):
            rels = []
            for subset in data['set'].keys():
                subrecord = cls.update_set (data['set'][subset], request, parent=record)
        elif (data.has_key ('module')):
            rels = []
            for xml_data in data['module'].values():
                mod_data = {}
                for k in xml_data.keys():
                    if k[:4] == 'scm_':
                        mod_data[str(k)] = xml_data[k]
                checkout = blip.scm.Repository (checkout=False, update=False, **mod_data)
                servername = checkout.server_name
                if servername == None:
                    continue
                if mod_data.get ('scm_branch', '') == '':
                    mod_data['scm_branch'] = checkout.scm_branch
                if mod_data.get ('scm_branch', '') == '':
                    continue
                ident = u'/'.join (['/mod', servername, mod_data['scm_module'], mod_data['scm_branch']])
                branch = blip.db.Branch.get_or_create (ident, u'Module')
                branch.update (mod_data)
                rels.append (blip.db.SetModule.set_related (record, branch))
            record.set_relations (blip.db.SetModule, rels)

        for sweeper in SetSweeper.get_extensions ():
            sweeper.sweep_set (record, data, request)

        return record
