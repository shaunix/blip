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

import inspect
import os
import shutil
import sys
import xml.dom.minidom

import pulse.db
import pulse.scm
import pulse.xmldata

synop = 'find icons in icon themes'
args = pulse.utils.odict()
args['no-update']  = (None, 'do not update SCM checkouts')

def get_theme_icons (data, icons, update=True):
    checkout = pulse.scm.Checkout (scm_type=data['scm_type'],
                                   scm_server=data['scm_server'],
                                   scm_module=data['scm_module'],
                                   scm_branch=data['scm_branch'],
                                   update=update)
    dir = os.path.join (checkout.directory, data['scm_dir'])
    def visit (arg, dirname, names):
        names.remove (checkout.ignoredir)
        for name in names:
            filename = os.path.join (dirname, name)
            if not (os.path.isfile (filename) and name.endswith ('.png')):
                continue
            icon_name = name[:-4]
            if not icons.has_key (icon_name):
                icons[icon_name] = filename
    os.path.walk (dir, visit, None)

def get_naming_links (data, links, update=True):
    checkout = pulse.scm.Checkout (scm_type=data['scm_type'],
                                   scm_server=data['scm_server'],
                                   scm_module=data['scm_module'],
                                   scm_branch=data.get('scm_branch'),
                                   update=update)
    fname = os.path.join (checkout.directory, data['scm_dir'], data['scm_file'])
    dom = xml.dom.minidom.parse (fname)
    for context in dom.getElementsByTagName ('context'):
        for icon in context.childNodes:
            if icon.nodeType != icon.ELEMENT_NODE or icon.tagName != 'icon':
                continue
            for link in icon.childNodes:
                if link.nodeType != link.ELEMENT_NODE or link.tagName != 'link':
                    continue
                if not links.has_key (link.firstChild.data):
                    links[link.firstChild.data] = icon.getAttribute ('name')

def update_installed_icons (icons, links):
    icondir = os.path.join (pulse.config.web_icons_dir, 'apps')
    if not os.path.exists (icondir):
        return
    for f in os.listdir (icondir):
        full = os.path.join (icondir, f)
        if not (os.path.isfile (full) and f.endswith ('.png')):
            continue
        name = f[:-4]
        if icons.has_key (name):
            iconsrc = name
        elif links.has_key (name):
            iconsrc = links[name]
            if not icons.has_key (iconsrc):
                continue
        else:
            continue
        if os.stat(icons[iconsrc]).st_mtime > os.stat(full).st_mtime:
            shutil.copyfile (icons[iconsrc], full)

def update_uninstalled_icons (icons, links):
    icondir = os.path.join (pulse.config.web_icons_dir, 'apps')
    if not os.path.exists (icondir):
        os.makedirs (icondir)
    for table in inspect.getmembers (pulse.db):
        cls = table[1]
        if (inspect.isclass (cls) and issubclass (cls, pulse.db.PulseModel)
            and hasattr (cls, '__storm_table__') and hasattr (cls, 'icon_dir')):
            recs = cls.select (icon_dir=u'__icon__:apps')
            for rec in recs:
                if rec.icon_name == None:
                    continue
                if icons.has_key (rec.icon_name):
                    iconsrc = rec.icon_name
                elif links.has_key (rec.icon_name):
                    iconsrc = links[rec.icon_name]
                    if not icons.has_key (iconsrc):
                        continue
                else:
                    continue
                shutil.copyfile (icons[iconsrc],
                                 os.path.join (icondir, rec.icon_name + '.png'))
                rec.icon_dir = u'apps'

def main (argv, options=None):
    if options is None:
        options = {}
    update = not options.get ('--no-update', False)

    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'icons.xml'))

    icons = {}
    links = {}
    for key in data.keys():
        if data[key]['__type__'] == 'theme':
            get_theme_icons (data[key], icons, update=update)
        elif data[key]['__type__'] == 'naming':
            get_naming_links (data[key], links, update=update)

    try:
        update_installed_icons (icons, links)
        update_uninstalled_icons (icons, links)
        pulse.db.flush ()
    except:
        pulse.db.rollback ()
        raise
    else:
        pulse.db.commit ()

    return 0
