# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
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

import os
import sys

import pulse.db
import pulse.scm
import pulse.utils
import pulse.xmldata

synop = 'update information from Gnome\'s jhbuild module'
def usage (fd=sys.stderr):
    print >>fd, ('Usage: %s' % sys.argv[0])

checkouts = {}

def update_set (data):
    ident = 'set/' + data['id']
    res = pulse.db.Resource.selectBy (ident=ident)
    if res.count() > 0:
        res = res[0]
    else:
        pulse.utils.log ('Creating resource %s' % ident)
        res = pulse.db.Resource (ident=ident, type='Set')

    if data.has_key ('set'):
        for key in data['set'].keys():
            subres = update_set (data['set'][key])
            pulse.db.set_relation (res, 'subset', subres)

    if (data.has_key ('jhbuild_scm_type')   and
        data.has_key ('jhbuild_scm_server') and
        data.has_key ('jhbuild_scm_module') and
        data.has_key ('jhbuild_scm_branch') and
        data.has_key ('jhbuild_scm_dir')    and
        data.has_key ('jhbuild_scm_file')   and
        data.has_key ('jhbuild_metamodule') ):

        ident = '/' + '/'.join (['jhbuild',
                                 data['jhbuild_scm_type'],
                                 data['jhbuild_scm_server'],
                                 data['jhbuild_scm_module'],
                                 data['jhbuild_scm_branch']])
        if checkouts.has_key (ident):
            checkout = checkouts[ident]
        else:
            checkout = pulse.scm.Checkout (ident=ident,
                                           scm_type=data['jhbuild_scm_type'],
                                           scm_server=data['jhbuild_scm_server'],
                                           scm_module=data['jhbuild_scm_module'],
                                           scm_branch=data['jhbuild_scm_branch'],
                                           update=True)
            checkouts[ident] = checkout
        # if ['jhbuild_metamodule'], add ->contains-> each branch

    return res

def main (argv):
    update = True
    like = None

    data = pulse.xmldata.get_data (os.path.join (pulse.config.datadir, 'xml', 'sets.xml'))

    for key in data.keys():
        if data[key]['__type__'] == 'set':
            update_set (data[key])
