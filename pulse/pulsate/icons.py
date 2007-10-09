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
import shutil
import sys

import pulse.db
import pulse.scm
import pulse.xmldata

synop = 'find icons in icon themes'
def usage (fd=sys.stderr):
    print >>fd, ('Usage: %s icons' % sys.argv[0])

def get_theme_icons (data, icons, update=True):
    checkout = pulse.scm.Checkout (scm_type=data['scm_type'],
                                   scm_server=data['scm_server'],
                                   scm_module=data['scm_module'],
                                   scm_branch=data['scm_branch'],
                                   update=update)
    dir = os.path.join (checkout.directory, data['scm_dir'])
    for f in os.listdir (dir):
        full = os.path.join (dir, f)
        if not (os.path.isfile (full) and f.endswith ('.png')):
            continue
        name = f[:-4]
        if not icons.has_key (name):
            icons[name] = full

def update_installed_icons (icons):
    icondir = os.path.join (pulse.config.icondir, 'apps')
    for f in os.listdir (icondir):
        full = os.path.join (icondir, f)
        if not (os.path.isfile (full) and f.endswith ('.png')):
            continue
        name = f[:-4]
        if not icons.has_key (name):
            continue
        if os.stat(icons[name]).st_mtime > os.stat(full).st_mtime:
            shutil.copyfile (icons[name], full)

def update_uninstalled_icons (icons):
    resources = pulse.db.Resource.selectBy (icon_dir='__icon__:apps')
    for resource in resources:
        if resource.icon_name == None:
            continue
        if icons.has_key (resource.icon_name):
            shutil.copyfile (icons[resource.icon_name],
                             os.path.join (pulse.config.icondir, 'apps', resource.icon_name + '.png'))
            resource.icon_dir = 'apps'

def main (argv):
    update = True
    if len (argv) > 2:
        for arg in argv[2:]:
            if arg.startswith ('-'):
                if arg == '--no-update':
                    update = False

    data = pulse.xmldata.get_data (os.path.join (pulse.config.datadir, 'xml', 'icons.xml'))

    icons = {}
    for key in data.keys():
        if data[key]['__type__'] == 'theme':
            get_theme_icons (data[key], icons, update=update)

    update_installed_icons (icons)
    update_uninstalled_icons (icons)
    return
    resources = pulse.db.Resource.select (pulse.db.Resource.q.icon.startswith ('icon://'))
    for resource in resources:
        # see if one of the icon themes has the icon and use it
        print resource.icon[7:]
