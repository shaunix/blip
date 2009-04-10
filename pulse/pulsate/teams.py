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

import datetime
import Image
import os
import urllib

import pulse.db
import pulse.graphs
import pulse.pulsate
import pulse.pulsate.people
import pulse.xmldata

synop = 'update information about teams'
args = pulse.utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')


def update_teams (**kw):
    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'teams.xml'))
    for key in data.keys():
        if not data[key]['__type__'] == 'team':
            continue
        if not data[key].has_key ('id'):
            continue
        ident = u'/team/' + data[key]['id']
        team = pulse.db.Entity.get_or_create (ident, u'Team')

        parent = data[key].get ('parent', None)
        if parent != None:
            team.parent = pulse.db.Entity.get_or_create (parent, u'Team')

        aliases = data[key].get ('alias', [])

        for alias in aliases:
            pulse.db.Alias.update_alias (team, alias)

        coords = data[key].get ('coordinators', [])
        if isinstance (coords, list) and len(coords) > 0:
            rels = []
            for coord in coords:
                entity = pulse.db.Entity.get_or_create (coord, u'Person')
                rel = pulse.db.TeamMember.set_related (team, entity, coordinator=True)
                rels.append (rel)
            team.set_relations (pulse.db.TeamMember, rels)
        else:
            team.set_relations (pulse.db.TeamMember, [])

        for k in ('name', 'web', 'blog'):
            if data[key].has_key (k):
                team.update(**{k : data[key][k]})
        if data[key].has_key ('icon'):
            update_icon (team, data[key]['icon'], 'teams')


def update_icon (team, href, icondir, **kw):
    # FIXME: we really shouldn't redownload these every time,
    # but we want to make sure we get updated versions.  Check
    # into using timestamps and If-Modified-Since
    iconname = urllib.quote ('/'.join (team.ident.split('/')[2:]), '')
    iconpath = os.path.join (pulse.config.web_icons_dir, icondir)
    iconorig = os.path.join (iconpath, iconname + '@@original.png')
    if not os.path.isdir (iconpath):
        os.makedirs (iconpath)
    urllib.urlretrieve (href, iconorig)
    im = Image.open (iconorig)
    im.thumbnail((36, 36), Image.ANTIALIAS)
    im.save (os.path.join (iconpath, iconname + '.png'), 'PNG')
    team.update ({'icon_dir' : icondir, 'icon_name' : iconname})


################################################################################
## main

def main (argv, options=None):
    if options is None:
        options = {}
    timestamps = not options.get ('--no-timestamps', False)

    update_teams (timestamps=timestamps)

    return 0

