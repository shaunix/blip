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
import os.path
import shutil
import sys

import xml.dom.minidom

import pulse.db
import pulse.scm
import pulse.parsers
import pulse.utils

synop = 'update information from module and branch checkouts'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only modules and branches with a matching identifier will be updated.'


def update_branch (branch, update=True, timestamps=True):
    checkout = pulse.scm.Checkout.from_record (branch, update=update)
    # FIXME: what do we want to know?
    # find maintainers
    # find document (in documents.py?)
    # find human-readable names for the module
    # mailing list
    # bug information
    podirs = []
    pkgconfigs = []
    oafservers = []
    keyfiles = []
    images = []
    gdu_docs = []
    gtk_docs = []
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
            elif name.endswith ('.desktop.in') or name.endswith ('.desktop.in.in'):
                keyfiles.append (filename)
            elif name.endswith ('.server.in.in'):
                oafservers.append (filename)
            elif name.endswith ('.png'):
                images.append (filename)
            elif name == 'Makefile.am':
                # FIXME: timestamp this
                makefile = pulse.parsers.Automake (filename)
                for line in makefile.get_lines():
                    if line.startswith ('include $(top_srcdir)/'):
                        if line.endswith ('gnome-doc-utils.make'):
                            gdu_docs.append((dirname, makefile))
                        elif line.endswith ('gtk-doc.make'):
                            gtk_docs.append((dirname, makefile))
    os.path.walk (checkout.directory, visit, None)

    process_configure (branch, checkout, timestamps=timestamps)
    if branch.name == {}:
        branch.name = {'C' : branch.scm_module}

    process_maintainers (branch, checkout, timestamps=timestamps)

    domains = []
    for podir in podirs:
        domain = process_podir (branch, checkout, podir, timestamps=timestamps)
        if domain != None:
            domains.append (domain)
    branch.set_children ('Domain', domains)

    documents = []
    for docdir, makefile in gdu_docs:
        document = process_gdu_docdir (branch, checkout, docdir, makefile, timestamps=timestamps)
        if document != None:
            documents.append (document)
    for docdir, makefile in gtk_docs:
        document = process_gtk_docdir (branch, checkout, docdir, makefile, timestamps=timestamps)
        if document != None:
            documents.append (document)
    branch.set_children ('Document', documents)

    default_resource = None

    libraries = []
    for pkgconfig in pkgconfigs:
        lib = process_pkgconfig (branch, checkout, pkgconfig, timestamps=timestamps)
        if lib != None:
            libraries.append (lib)
    branch.set_children ('Library', libraries)

    applications = []
    for keyfile in keyfiles:
        try:
            app = process_keyfile (branch, checkout, keyfile, images=images, timestamps=timestamps)
        except:
            # FIXME: log something
            app = None
        if app != None:
            if default_resource == None:
                if app.ident.split('/')[-1] == branch.scm_module:
                    default_resource = app
            applications.append (app)
    branch.set_children ('Application', applications)

    applets = []
    for oafserver in oafservers:
        applets += process_oafserver (branch, checkout, oafserver, images=images, timestamps=timestamps)
    branch.set_children ('Applet', applets)

    if default_resource == None:
        if len(applications) == 1 and len(applets) == 0:
            default_resource = applications[0]
        elif len(applets) == 1 and len(applications) == 0:
            default_resource = applets[0]
        else:
            for app in applications:
                if app.data.get ('exec', None) == branch.scm_module:
                    default_resource = app
                    break

    if default_resource != None:
        branch.name = default_resource.name
        branch.desc = default_resource.desc
        branch.icon_dir = default_resource.icon_dir
        branch.icon_name = default_resource.icon_name
    

def process_maintainers (branch, checkout, **kw):
    maintfile = os.path.join (checkout.directory, 'MAINTAINERS')
    if not os.path.isfile (maintfile):
        return

    rel_scm = pulse.utils.relative_path (maintfile, pulse.config.scmdir)
    mtime = os.stat(maintfile).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        mtime = os.stat(maintfile).st_mtime
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    start = True
    name = None
    email = None
    userid = None
    maints = []
    def add_maint ():
        if name != None and userid != None:
            maints.append ((name, userid, email))
    for l in open (maintfile):
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
    serverid = '.'.join (pulse.scm.server_name (branch.scm_type, branch.scm_server).split('.')[-2:])
    rels = []
    for name, userid, email in maints:
        ident = '/person/' + serverid + '/' + userid
        person = pulse.db.Entity.get_record (ident=ident, type='Person')
        person.update_name ({'C' : name})
        if email != None:
            person.email = email
        rels.append (pulse.db.BranchEntityRelation.set_related (subj=branch,
                                                                verb='ModuleMaintainer',
                                                                pred=person))
    branch.set_relations (pulse.db.BranchEntityRelation, 'ModuleMaintainer', rels)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

def process_configure (branch, checkout, **kw):
    filename = os.path.join (checkout.directory, 'configure.in')
    if not os.path.exists (filename):
        filename = os.path.join (checkout.directory, 'configure.ac')
    if not os.path.exists (filename):
        return

    rel_scm = pulse.utils.relative_path (filename, pulse.config.scmdir)
    mtime = os.stat(filename).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)
                     
    functxts = {}
    infunc = None
    ac_inittxt = None
    am_inittxt = None
    for line in open (filename):
        if infunc != None:
            pass
        elif line.startswith ('AC_INIT('):
            infunc = 'AC_INIT'
            functxts[infunc] = ''
            line = line[8:]
        elif line.startswith ('AM_INIT_AUTOMAKE('):
            infunc = 'AM_INIT_AUTOMAKE'
            functxts[infunc] = ''
            line = line[17:]
        if infunc != None:
            rparen = line.find (')')
            if rparen >= 0:
                functxts[infunc] += line[:rparen]
                infunc = None
            else:
                functxts[infunc] += line.strip()
    initargs = functxts['AC_INIT'].split(',')
    if len(initargs) < 2:
        initargs = functxts['AM_INIT_AUTOMAKE'].split(',')
    for i in range(len(initargs)):
        arg = initargs[i]
        arg = arg.strip()
        if arg[0] == '[' and arg[-1] == ']':
            arg = arg[1:-1]
        arg = arg.strip()
        initargs[i] = arg
    data = {'tarversion' : initargs[1]}
    if len(initargs) >= 4:
        data['tarname'] = initargs[3]
    else:
        data['tarname'] = initargs[0]
    branch.update (data)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

def process_podir (branch, checkout, podir, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    ident = '/'.join(['/i18n', bserver, bmodule, os.path.basename (podir), bbranch])
    domain = pulse.db.Branch.get_record (ident=ident, type='Domain')

    data = {'scm_dir' : pulse.utils.relative_path (podir, checkout.directory)}
    domain.update (data)

    linguas = os.path.join (podir, 'LINGUAS')
    if not os.path.isfile (linguas):
        return domain

    rel_scm = pulse.utils.relative_path (linguas, pulse.config.scmdir)
    mtime = os.stat(linguas).st_mtime
    langs = []
    translations = []

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return domain
    pulse.utils.log ('Processing file %s' % rel_scm)

    fd = open (linguas)
    for line in fd:
        if line.startswith ('#') or line == '\n':
            continue
        for l in line.split():
            langs.append (l)
    for lang in langs:
        lident = '/l10n/' + lang + domain.ident
        translation = pulse.db.Branch.get_record (ident=lident, type='Translation')
        translations.append (translation)
        ldata = {}
        ldata['subtype'] = 'intltool'
        ldata['scm_dir'] = data['scm_dir']
        ldata['scm_file'] = lang + '.po'
        translation.update (ldata)
    domain.set_children ('Translation', translations)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return domain

def process_gdu_docdir (branch, checkout, docdir, makefile, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    doc_module = makefile['DOC_MODULE']
    ident = '/'.join(['/doc', bserver, bmodule, doc_module, bbranch])
    document = pulse.db.Branch.get_record (ident=ident, type='Document')
    relpath = pulse.utils.relative_path (docdir, checkout.directory)

    data = {}
    data['subtype'] = 'gdu-docbook'
    data['scm_dir'] = os.path.join (relpath, 'C')
    data['scm_file'] = doc_module + '.xml'
    document.update (data)

    if makefile.has_key ('DOC_LINGUAS'):
        translations = []
        for lang in makefile['DOC_LINGUAS'].split():
            lident = '/l10n/' + lang + document.ident
            translation = pulse.db.Branch.get_record (ident=lident, type='Translation')
            translations.append (translation)
            ldata = {}
            ldata['subtype'] = 'xml2po'
            ldata['scm_dir'] = os.path.join (pulse.utils.relative_path (docdir, checkout.directory), lang)
            ldata['scm_file'] = lang + '.po'
            translation.update (ldata)
        document.set_children ('Translation', translations)
    return document

def process_gtk_docdir (branch, checkout, docdir, makefile, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    doc_module = makefile['DOC_MODULE']
    ident = '/'.join(['/ref', bserver, bmodule, doc_module, bbranch])
    document = pulse.db.Branch.get_record (ident=ident, type='Document')
    document.update ({'subtype' : 'gtk-doc'})
    return document

def process_pkgconfig (branch, checkout, filename, **kw):
    basename = os.path.basename (filename)[:-6]
    rel_ch = pulse.utils.relative_path (filename, checkout.directory)
    rel_scm = pulse.utils.relative_path (filename, pulse.config.scmdir)
    mtime = os.stat(filename).st_mtime
    # Hack for GTK+'s uninstalled pkgconfig files
    if '-uninstalled' in basename:
        return None

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            data = {'parent' : branch}
            data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
            libs = pulse.db.Branch.selectBy (type='Library', **data)
            if libs.count() > 0:
                return libs[0]
            else:
                return None
    pulse.utils.log ('Processing file %s' % rel_scm)

    libname = ''
    libdesc = ''
    for line in open (filename):
        if line.startswith ('Name:'):
            libname = line[5:].strip()
        elif line.startswith ('Description:'):
            libdesc = line[12:].strip()

    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    ident = '/'.join(['/lib', bserver, bmodule, basename, bbranch])
    lib = pulse.db.Branch.get_record (ident=ident, type='Library')

    if libname == '@PACKAGE_NAME@':
        libname = branch.name['C']
    
    lib.update_name ({'C' : libname})
    lib.update_desc ({'C' : libdesc})

    data = {}
    data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
    lib.update (data)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return lib

def process_keyfile (branch, checkout, filename, **kw):
    rel_ch = pulse.utils.relative_path (filename, checkout.directory)
    rel_scm = pulse.utils.relative_path (filename, pulse.config.scmdir)
    mtime = os.stat(filename).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            data = {'parent' : branch}
            data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
            apps = pulse.db.Branch.selectBy (type='Application', **data)
            if apps.count() > 0:
                return apps[0]
            else:
                return None
    pulse.utils.log ('Processing file %s' % rel_scm)
                     
    if filename.endswith ('.desktop.in.in'):
        basename = os.path.basename (filename)[:-14]
    else:
        basename = os.path.basename (filename)[:-11]
    owd = os.getcwd ()
    try:
        os.chdir (checkout.directory)
        keyfile = pulse.parsers.KeyFile (os.popen ('LC_ALL=C intltool-merge -d -q -u po "' + rel_ch + '" -'))
    finally:
        os.chdir (owd)
    if not keyfile.has_group ('Desktop Entry'):
        return None
    if not keyfile.has_key ('Desktop Entry', 'Type'):
        return None
    if keyfile.get_value ('Desktop Entry', 'Type') != 'Application':
        return None

    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    ident = '/'.join(['/app', bserver, bmodule, basename, bbranch])

    name = keyfile.get_value ('Desktop Entry', 'Name')
    if isinstance (name, basestring):
        name = {'C' : name}

    if keyfile.has_key ('Desktop Entry', 'Comment'):
        desc = keyfile.get_value ('Desktop Entry', 'Comment')
        if isinstance (desc, basestring):
            desc = {'C' : desc}
    else:
        desc = None

    app = pulse.db.Branch.get_record (ident=ident, type='Application')

    data = {}
    data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
    app.update (data)

    app.update_name (name)
    if desc != None:
        app.update_desc (desc)
    if keyfile.has_key ('Desktop Entry', 'Icon'):
        locate_icon (app,
                     keyfile.get_value ('Desktop Entry', 'Icon'),
                     kw.get ('images', []))

    if keyfile.has_key ('Desktop Entry', 'Exec'):
        app.update_data ({'exec' : keyfile.get_value ('Desktop Entry', 'Exec')})

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return app

def process_oafserver (branch, checkout, filename, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    basename = os.path.basename (filename)[:-13]
    rel_ch = pulse.utils.relative_path (filename, checkout.directory)
    rel_scm = pulse.utils.relative_path (filename, pulse.config.scmdir)
    mtime = os.stat(filename).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            data = {'parent' : branch}
            data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
            applets = pulse.db.Branch.selectBy (type='Applet', **data)
            return applets[0:]
    pulse.utils.log ('Processing file %s' % rel_scm)

    owd = os.getcwd ()
    applets = []
    pulse.utils.log ('Processing file %s' %
                     pulse.utils.relative_path (filename, pulse.config.scmdir))
    try:
        os.chdir (checkout.directory)
        dom = xml.dom.minidom.parse (os.popen ('LC_ALL=C intltool-merge -x -q -u po "' + rel_ch + '" -'))
    finally:
        os.chdir (owd)
    for server in dom.getElementsByTagName ('oaf_server'):
        is_applet = False
        applet_name = {}
        applet_desc = {}
        applet_icon = None
        applet_iid = server.getAttribute ('iid')
        if applet_iid == '': continue
        if applet_iid.startswith ('OAFIID:'):
            applet_iid = applet_iid[7:]
        if applet_iid.startswith ('GNOME_'):
            applet_iid = applet_iid[6:]
        for oafattr in server.childNodes:
            if oafattr.nodeType != oafattr.ELEMENT_NODE or oafattr.tagName != 'oaf_attribute':
                continue
            if oafattr.getAttribute ('name') == 'repo_ids':
                for item in oafattr.childNodes:
                    if item.nodeType != item.ELEMENT_NODE or item.tagName != 'item':
                        continue
                    if item.getAttribute ('value') == 'IDL:GNOME/Vertigo/PanelAppletShell:1.0':
                        is_applet = True
                        break
                if not is_applet:
                    break
            if oafattr.getAttribute ('name') == 'name':
                lang = oafattr.getAttribute ('xml:lang')
                if lang == '': lang = 'C'
                value = oafattr.getAttribute ('value')
                if value != '':
                    applet_name[lang] = value
            if oafattr.getAttribute ('name') == 'description':
                lang = oafattr.getAttribute ('xml:lang')
                if lang == '': lang = 'C'
                value = oafattr.getAttribute ('value')
                if value != '':
                    applet_desc[lang] = value
            if oafattr.getAttribute ('name') == 'panel:icon':
                applet_icon = oafattr.getAttribute ('value')
                if applet_icon == '': applet_icon = None
        if not is_applet or applet_icon == None:
            continue
        ident = '/'.join(['/applet', bserver, bmodule, applet_iid, bbranch])
        applet = pulse.db.Branch.get_record (ident=ident, type='Applet')
        applet.update_name (applet_name)
        applet.update_desc (applet_desc)
        if applet_icon != None:
            locate_icon (applet, applet_icon, kw.get ('images', []))

        data = {}
        data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
        applet.update (data)

        applets.append (applet)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return applets

def locate_icon (resource, icon, images):
    icondir = os.path.join (pulse.config.icondir, 'apps')

    if icon.endswith ('.png'):
        iconfile = icon
        icon = icon[:-4]
    else:
        iconfile = icon + '.png'
    candidates = []
    for img in images:
        if os.path.basename (img) == iconfile:
            candidates.append (img)
    use = None
    for img in candidates:
        if '24x24' in img:
            use = img
            break
    # FIXME: try actually looking at sizes, pick closest
    if use != None:
        if not os.path.isdir (icondir):
            os.makedirs (icondir)
        shutil.copyfile (use, os.path.join (icondir, os.path.basename (use)))
        resource.update ({'icon_dir' : 'apps', 'icon_name' : os.path.basename (use[:-4])})
    elif resource.icon_name == None or resource.icon_name != icon:
        resource.update ({'icon_dir' : '__icon__:apps', 'icon_name' : icon})

def main (argv, options={}):
    update = not options.get ('--no-update', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix != None:
        if prefix[:5] == '/set/':
            sets = pulse.db.Record.select ((pulse.db.Record.q.type == 'Set') &
                                           (pulse.db.Record.q.ident.startswith (prefix)) )
            branches = []
            for set in sets:
                rels = pulse.db.RecordBranchRelation.selectBy (subj=set, verb='SetModule')
                for rel in rels:
                    branches.append (rel.pred)
        else:
            branches = pulse.db.Branch.select ((pulse.db.Branch.q.type == 'Module') &
                                               (pulse.db.Branch.q.ident.startswith (prefix)) )
    else:
        branches = pulse.db.Branch.selectBy (type='Module')

    for branch in branches:
        update_branch (branch, update=update, timestamps=timestamps)
