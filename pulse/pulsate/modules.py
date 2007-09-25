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

import xml.dom.minidom

import pulse.db
import pulse.scm

synop = 'update information module and branch checkouts'
def usage (fd=sys.stderr):
    print >>fd, ('Usage: %s [PREFIX]' % sys.argv[0])

def update_branch (resource, update):
    checkout = pulse.scm.Checkout (update=update, **resource.data)
    # FIXME: what do we want to know?
    # find maintainers
    # find document (in documents.py?)
    # find domains (in i18n.py?)
    # find human-readable names for the module
    # mailing list
    # icon
    # but branch names should be MODULE (BRANCH)
    # bug information
    # We can get much of this from a .desktop file for apps, if we can find it
    keyfiles = []
    def visit (arg, dirname, names):
        names.remove (checkout.ignoredir)
        for name in names:
            file = os.path.join (dirname, name)
            if not os.path.isfile (file):
                continue
            if name == 'POTFILES.in':
                process_podir (resource, checkout, dirname)
            if name.endswith ('.desktop.in.in'):
                keyfiles.append (file)
    os.path.walk (checkout.directory, visit, None)

    for keyfile in keyfiles:
        process_keyfile (resource, checkout, keyfile)

    for res in (res, res.parent):
        if res.name == {}:
            res.name = {'C', res.ident.split('/')[3]}

def process_podir (resource, checkout, dir):
    ident = '/' + '/'.join (['i18n'] +
                            resource.ident.split('/')[2:] +
                            [os.path.basename (dir)])
    domain = pulse.db.Resource.make (ident=ident, type='Domain')
    domain.parent = resource

    data = {}
    data['directory'] = dir[len(checkout.directory)+1:]
    domain.update_data (data)

def process_keyfile (resource, checkout, file):
    basename = os.path.basename(file)[0:-14]
    relfile = file[len(checkout.directory)+1:]
    owd = os.getcwd ()
    try:
        os.chdir (checkout.directory)
        keyfile = pulse.utils.keyfile (os.popen ('LC_ALL=C intltool-merge -d -q -u po "' + relfile + '" -'))
    finally:
        os.chdir (owd)
    if not keyfile.has_group ('Desktop Entry'):
        return
    if not keyfile.has_key ('Desktop Entry', 'Type'):
        return
    if keyfile.get_value ('Desktop Entry', 'Type') != 'Application':
        return
    ident = '/' + '/'.join (['app'] +
                            resource.ident.split('/')[2:] +
                            [basename])
    name = keyfile.get_value ('Desktop Entry', 'Name')
    desc = keyfile.get_value ('Desktop Entry', 'Comment')
    data = {'keyfile' : relfile}
    app = pulse.db.Resource.make (ident=ident, type='Application')
    app.update_name (name)
    app.update_desc (desc)
    app.update_data (data)
    # FIXME: icon, bugzilla stuff

    if basename == resource.ident.split('/')[3]:
        resource.update_name (name)
        resource.update_desc (desc)
        resource.update_data (data)

def main (argv):
    update = True
    prefix = None
    if len (argv) > 2:
        for arg in argv[2:]:
            if arg.startswith ('-'):
                if arg == '--no-update':
                    update = False
            else:
                prefix = arg

    if prefix != None:
        branches = pulse.db.Resource.select ((pulse.db.Resource.q.type == 'Branch') &
                                             (pulse.db.Resource.q.ident.startswith (prefix)) )
    else:
        branches = pulse.db.Resource.selectBy (type='Branch')

    for branch in branches:
        update_branch (branch, update)
