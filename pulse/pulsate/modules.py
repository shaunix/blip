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
    podirs = []
    pkgconfigs = []
    keyfiles = []
    images = []
    gdu_docs = []
    def visit (arg, dirname, names):
        names.remove (checkout.ignoredir)
        for name in names:
            filename = os.path.join (dirname, name)
            if not os.path.isfile (filename):
                continue
            if name == 'POTFILES.in':
                podirs.append (dirname)
            elif name.endswith ('.pc.in'):
                pkgconfigs.append (filename)
            elif name.endswith ('.desktop.in.in'):
                keyfiles.append (filename)
            elif name.endswith ('.png'):
                images.append (filename)
            elif name == 'Makefile.am':
                fd = open (filename)
                makefile = pulse.utils.makefile (fd)
                fd.close()
                if 'include $(top_srcdir)/gnome-doc-utils.make' in makefile.get_lines():
                    gdu_docs.append((dirname, makefile))
    os.path.walk (checkout.directory, visit, None)

    process_configure (branch, checkout)
    if branch.name == {}:
        branch.name = {'C' : branch.ident.split('/')[3]}

    domains = []
    for podir in podirs:
        domain = process_podir (branch, checkout, podir)
        if domain != None:
            domains.append (domain)
    branch.set_children ('Domain', domains)

    documents = []
    for docdir, makefile in gdu_docs:
        document = process_gdu_docdir (branch, checkout, docdir, makefile)
        if document != None:
            documents.append (document)
    branch.set_children ('Document', documents)

    libraries = []
    for pkgconfig in pkgconfigs:
        lib = process_pkgconfig (branch, checkout, pkgconfig)
        if lib != None:
            libraries.append (lib)
    branch.set_children ('Library', libraries)

    applications = []
    for keyfile in keyfiles:
        app = process_keyfile (branch, checkout, keyfile, images=images)
        if app != None:
            applications.append (app)
    branch.set_children ('Application', applications)

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

def process_configure (branch, checkout):
    fname = os.path.join (checkout.directory, 'configure.in')
    if not os.path.exists (fname):
        fname = os.path.join (checkout.directory, 'configure.ac')
    if not os.path.exists (fname):
        return

    inittxt = None
    for line in open (fname):
        if line.startswith ('AC_INIT('):
            inittxt = ''
            line = line[8:]
        if inittxt != None:
            rparen = line.find (')')
            if rparen >= 0:
                inittxt += line[:rparen]
                break
            else:
                inittxt += line.strip()
    initargs = inittxt.split(',')
    for i in range(len(initargs)):
        arg = initargs[i]
        arg = arg.strip().rstrip()
        if arg[0] == '[' and arg[-1] == ']':
            arg = arg[1:-1]
        arg = arg.strip().rstrip()
        initargs[i] = arg
    if branch.name == {} or branch.name == {'C' : branch.ident.split('/')[3]}:
        branch.name = {'C' : initargs[0]}
    data = {'tarversion' : initargs[1]}
    if len(initargs) >= 4:
        data['tarname'] = initargs[3]
    else:
        data['tarname'] = initargs[0]
    branch.update_data (data)

def process_podir (branch, checkout, podir):
    ident = '/i18n/' + '/'.join (branch.ident.split('/')[2:]) + '/' + os.path.basename (podir)
    domain = pulse.db.Resource.make (ident=ident, type='Domain')

    data = {}
    for key in branch.data.keys():
        if key.startswith ('scm_'):
            data[key] = branch.data[key]
    data['directory'] = podir[len(checkout.directory)+1:]
    domain.update_data (data)

    linguas = os.path.join (podir, 'LINGUAS')
    langs = []
    translations = []
    if os.path.isfile (linguas):
        fd = open (linguas)
        for line in fd:
            if line.startswith ('#') or line == '\n':
                continue
            langs.append (line.strip ())
    for lang in langs:
        lident = '/i18n/' + '/'.join (branch.ident.split('/')[2:]) + '/po/' + os.path.basename (podir) + '/' + lang
        translation = pulse.db.Resource.make (ident=lident, type='Translation')
        translations.append (translation)
        ldata = data
        ldata['file'] = lang + '.po'
        translation.update_data (data)
    domain.set_children ('Translation', translations)

    return domain

def process_gdu_docdir (branch, checkout, docdir, makefile, **kw):
    doc_module = makefile['DOC_MODULE']
    ident = '/doc/' + '/'.join(branch.ident.split('/')[2:5]) + '/' + doc_module
    document = pulse.db.Resource.make (ident=ident, type='Document')
    document.update_data ({'document_tool' : 'gnome-doc-utils'})
    return document

def process_pkgconfig (branch, checkout, filename, **kw):
    basename = os.path.basename (filename)[:-6]
    # Hack for GTK+'s uninstalled pkgconfig files
    if '-uninstalled' in basename:
        return None
    islib = False
    libname = ''
    libdesc = ''
    for line in open (filename):
        if line.startswith ('Libs:'):
            islib = True
        elif line.startswith ('Name:'):
            libname = line[5:].strip().rstrip()
        elif line.startswith ('Description:'):
            libdesc = line[12:].strip().rstrip()

    if not islib:
        return None

    ident = '/lib/' + '/'.join (branch.ident.split('/')[2:]) + '/' + basename
    lib = pulse.db.Resource.make (ident=ident, type='Library')

    if libname == '@PACKAGE_NAME@':
        libname = branch.name['C']
    
    lib.update_name ({'C' : libname})
    lib.update_desc ({'C' : libdesc})

    data = {'pkgconfig' : filename[len(checkout.directory)+1:]}
    lib.update_data (data)

    return lib

def process_keyfile (branch, checkout, filename, **kw):
    basename = os.path.basename (filename)[:-14]
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
    ident = '/app/' + '/'.join (branch.ident.split('/')[2:]) + '/' + basename
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

    icon = None
    if keyfile.has_key ('Desktop Entry', 'Icon'):
        iconfile = keyfile.get_value ('Desktop Entry', 'Icon')
        if not iconfile.endswith ('.png'):
            iconfile += '.png'
        candidates = []
        for img in kw.get ('images', []):
            if os.path.basename (img) == iconfile:
                candidates.append (img)
        use = None
        for img in candidates:
            if '24x24' in img:
                use = img
                break
        # FIXME: try actually looking at sizes, pick closest
        if use != None:
            shutil.copyfile (use, os.path.join (pulse.config.icondir, os.path.basename (use)))
            icon = os.path.basename (use)
        else:
            # try looking in gnome-icon-theme
            pass

    app = pulse.db.Resource.make (ident=ident, type='Application')
    app.update_name (name)
    if desc != None:
        app.update_desc (desc)
    if icon != None:
        app.icon = icon
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
