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

def update_branch (branch, update):
    checkout = pulse.scm.Checkout (update=update, **branch.data)
    branch.nick = checkout.scm_branch
    # FIXME: what do we want to know?
    # find maintainers
    # find document (in documents.py?)
    # find human-readable names for the module
    # mailing list
    # icon
    # bug information
    domains = []
    keyfiles = []
    def visit (arg, dirname, names):
        names.remove (checkout.ignoredir)
        for name in names:
            filename = os.path.join (dirname, name)
            if not os.path.isfile (filename):
                continue
            if name == 'POTFILES.in':
                domain = process_podir (branch, checkout, dirname)
                if domain != None:
                    domains.append (domain)
            if name.endswith ('.desktop.in.in'):
                keyfiles.append (filename)
    os.path.walk (checkout.directory, visit, None)

    branch.set_children ('Domain', domains)

    applications = []
    for keyfile in keyfiles:
        app = process_keyfile (branch, checkout, keyfile)
        if app != None:
            applications.append (app)
    branch.set_children ('Application', applications)

    if branch.name == {}:
        branch.name = {'C' : branch.ident.split('/')[3]}

    if checkout.default:
        update_module_from_branch (branch, checkout)

def update_module_from_branch (branch, checkout):
    module = branch.parent
    module.update_name (branch.name)
    module.update_desc (branch.desc)

    if os.path.isfile (os.path.join (checkout.directory, 'MAINTAINERS')):
        start = True
        name = None
        email = None
        userid = None
        maints = []
        def add_maint ():
            if name != None and userid != None:
                maints.append ((name, userid, email))
        for l in open (os.path.join (checkout.directory, 'MAINTAINERS')):
            line = l.rstrip()
            if line.startswith ('#'):
                continue
            if line == "":
                add_maint ()
                name = email = userid = None
                start = True
                continue

            if start:
                name = line
                start = False
            elif line.startswith ('E-mail:'):
                email = line[7:].strip()
            elif line.startswith ('Userid:'):
                userid = line[7:].strip()
        add_maint ()
        serverid = module.ident.split('/')[2]
        rels = []
        for name, userid, email in maints:
            ident = '/person/' + serverid + '/' + userid
            person = pulse.db.Resource.make (ident=ident, type='Person')
            person.update_name ({'C' : name})
            if email != None:
                person.email = email
            rels.append (pulse.db.Relation.make (subj=module,
                                                 verb=pulse.db.Relation.module_developer,
                                                 pred=person,
                                                 superlative=True))
        module.set_relations (pulse.db.Relation.module_developer, rels)


def process_podir (branch, checkout, dir):
    ident = '/' + '/'.join (['i18n'] +
                            branch.ident.split('/')[2:] +
                            [os.path.basename (dir)])
    domain = pulse.db.Resource.make (ident=ident, type='Domain')

    data = {}
    data['directory'] = dir[len(checkout.directory)+1:]
    domain.update_data (data)

    return domain

def process_keyfile (branch, checkout, filename):
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
                            branch.ident.split('/')[2:] +
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

    if basename == branch.ident.split('/')[3]:
        branch.update_name (name)
        if desc != None:
            branch.update_desc (desc)
        branch.update_data (data)

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
