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

synop = 'update information from module and branch checkouts'
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
    domains = []
    keyfiles = []
    def visit (arg, dirname, names):
        names.remove (checkout.ignoredir)
        for name in names:
            filename = os.path.join (dirname, name)
            if not os.path.isfile (filename):
                continue
            if name == 'POTFILES.in':
                domain = process_podir (resource, checkout, dirname)
                if domain != None:
                    domains.append (domain)
            if name.endswith ('.desktop.in.in'):
                keyfiles.append (filename)
    os.path.walk (checkout.directory, visit, None)

    resource.set_children ('Domain', domains)

    applications = []
    for keyfile in keyfiles:
        app = process_keyfile (resource, checkout, keyfile)
        if app != None:
            applications.append (app)
    resource.set_children ('Application', applications)

    for res in (resource, resource.parent):
        if res.name == {}:
            res.name = {'C' : res.ident.split('/')[3]}

def process_podir (resource, checkout, dir):
    ident = '/' + '/'.join (['i18n'] +
                            resource.ident.split('/')[2:] +
                            [os.path.basename (dir)])
    domain = pulse.db.Resource.make (ident=ident, type='Domain')

    data = {}
    data['directory'] = dir[len(checkout.directory)+1:]
    domain.update_data (data)

    return domain

def process_keyfile (resource, checkout, filename):
    basename = os.path.basename(filename)[0:-14]
    relfile = filename[len(checkout.directory)+1:]
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
    if isinstance (name, basestring):
        name = {'C' : name}

    if keyfile.has_key ('Desktop Entry', 'Comment'):
        desc = keyfile.get_value ('Desktop Entry', 'Comment')
        if isinstance (desc, basestring):
            desc = {'C' : desc}
    else:
        desc = None

    data = {'keyfile' : relfile}
    app = pulse.db.Resource.make (ident=ident, type='Application')
    app.update_name (name)
    if desc != None:
        app.update_desc (desc)
    app.update_data (data)
    # FIXME: icon, bugzilla stuff

    if basename == resource.ident.split('/')[3]:
        resource.update_name (name)
        if desc != None:
            resource.update_desc (desc)
        resource.update_data (data)

    return app

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
