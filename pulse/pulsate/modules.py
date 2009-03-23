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

import commands
import datetime
import Image
import math
import os
import os.path
import re
import shutil
import sys

import xml.dom.minidom

import pulse.db
import pulse.graphs
import pulse.scm
import pulse.parsers
import pulse.pulsate
import pulse.utils

import pulse.pulsate.docs
import pulse.pulsate.i18n

synop = 'update information from module and branch checkouts'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-history'] = (None, 'do not check SCM history')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-docs'] = (None, 'do not update the documentation')
args['no-i18n'] = (None, 'do not update the translations')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only modules and branches with a matching identifier will be updated.'


def update_branch (branch, **kw):
    checkout = pulse.scm.Checkout.from_record (branch, update=kw.get('update', True))

    if checkout.error != None:
        branch.update(error=checkout.error)
        return
    else:
        branch.update(error=None)

    if kw.get('history', True):
        check_history (branch, checkout)

    pulse.pulsate.update_graphs (branch, {'branch' : branch}, 80, **kw)

    # FIXME: what do we want to know?
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
        for ignore in (checkout.ignoredir, 'examples', 'test', 'tests'):
            if ignore in names:
                names.remove (ignore)
        for name in names:
            filename = os.path.join (dirname, name)
            if not os.path.isfile (filename):
                continue
            if name == 'POTFILES.in':
                podirs.append (dirname)
            elif re.match('.*\.pc(\.in)+$', name):
                pkgconfigs.append (filename)
            elif re.match('.*\.desktop(\.in)+$', name):
                keyfiles.append (filename)
            elif re.match('.*\.server(\.in)+$', name):
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

    process_configure (branch, checkout, **kw)
    if branch.name == {}:
        branch.name = {'C' : branch.scm_module}

    process_maintainers (branch, checkout, **kw)

    domains = []
    for podir in podirs:
        domain = process_podir (branch, checkout, podir, **kw)
        if domain != None:
            domains.append (domain)
    branch.set_children (u'Domain', domains)

    documents = []
    for docdir, makefile in gdu_docs:
        document = process_gdu_docdir (branch, checkout, docdir, makefile, **kw)
        if document != None:
            documents.append (document)
    for docdir, makefile in gtk_docs:
        document = process_gtk_docdir (branch, checkout, docdir, makefile, **kw)
        if document != None:
            documents.append (document)
    branch.set_children (u'Document', documents)
    if kw.get('do_docs', True):
        for doc in documents:
            pulse.pulsate.docs.update_document (doc, checkout=checkout, **kw)

    default_child = None

    libraries = []
    for pkgconfig in pkgconfigs:
        lib = process_pkgconfig (branch, checkout, pkgconfig, **kw)
        if lib != None:
            libraries.append (lib)
    branch.set_children (u'Library', libraries)

    applications = []
    capplets = []
    for keyfile in keyfiles:
        try:
            app = process_keyfile (branch, checkout, keyfile, images=images, **kw)
        except:
            # FIXME: log something
            raise
            app = None
        if app != None:
            if app.type == 'Application':
                if default_child == None:
                    if app.ident.split('/')[-2] == branch.scm_module:
                        default_child = app
                applications.append (app)
            elif app.type == 'Capplet':
                capplets.append (app)
    branch.set_children (u'Application', applications)
    branch.set_children (u'Capplet', capplets)

    applets = []
    for oafserver in oafservers:
        applets += process_oafserver (branch, checkout, oafserver, images=images, **kw)
    branch.set_children (u'Applet', applets)

    for obj in (applications + capplets + applets):
        rels = pulse.db.Documentation.get_related (subj=obj)
        if len(rels) == 0: continue
        doc = rels[0].pred
        if doc.data.has_key ('screenshot'):
            obj.data['screenshot'] = doc.data['screenshot']

    if default_child == None:
        if len(applications) == 1 and len(applets) == 0:
            default_child = applications[0]
        elif len(applets) == 1 and len(applications) == 0:
            default_child = applets[0]
        elif len(applications) > 0:
            for app in applications:
                if app.data.get ('exec', None) == branch.scm_module:
                    default_child = app
                    break
        elif len(applets) > 0:
            pass
        elif len(capplets) == 1:
            default_child = capplets[0]

    if default_child != None:
        branch.name = default_child.name
        branch.desc = default_child.desc
        branch.icon_dir = default_child.icon_dir
        branch.icon_name = default_child.icon_name
        if default_child.data.has_key ('screenshot'):
            branch.data['screenshot'] = default_child.data['screenshot']
    else:
        branch.name = {'C' : branch.scm_module}
        branch.desc = {}
        branch.icon_dir = None
        branch.icon_name = None
        branch.data.pop ('screenshot', None)

    branch.updated = datetime.datetime.utcnow ()
    pulse.db.Queue.remove ('modules', branch.ident)
    

def check_history (branch, checkout):
    since = pulse.db.Revision.get_last_revision (branch=branch)
    if since != None:
        since = since.revision
        current = checkout.get_revision()
        if current != None and since == current[0]:
            pulse.utils.log ('Skipping history for %s' % branch.ident)
            return
    pulse.utils.log ('Checking history for %s' % branch.ident)
    serverid = u'.'.join (pulse.scm.server_name (checkout.scm_type, checkout.scm_server).split('.')[-2:])
    for hist in checkout.read_history (since=since):
        if hist['author'][0] != None:
            pident = u'/person/%s@%s' % (hist['author'][0], serverid)
            person = pulse.db.Entity.get_or_create (pident, u'Person')
        elif hist['author'][2] != None:
            person = pulse.db.Entity.get_or_create_email (hist['author'][2])
        else:
            pident = u'/ghost/%' % hist['author'][1]
            person = pulse.db.Entity.get_or_create (pident, u'Ghost')

        if person.type == u'Person':
            pulse.db.Queue.push (u'people', pident)
        if hist['author'][1] != None:
            person.extend (name=hist['author'][1])
        if hist['author'][2] != None:
            person.extend (email=hist['author'][2])
        # IMPORTANT: If we were to just set branch and person, instead of
        # branch_ident and person_ident, Storm would keep referencess to
        # the Revision object.  That would eat your computer.
        revident = branch.ident + u'/' + hist['revision']
        rev = {'ident': revident,
               'branch_ident': branch.ident,
               'person_ident': person.ident,
               'revision': hist['revision'],
               'datetime': hist['datetime'],
               'comment': hist['comment'] }
        if person.ident != pident:
            rev['alias_ident'] = pident
        if pulse.db.Revision.select(ident=revident).count() > 0:
            continue
        rev = pulse.db.Revision (**rev)
        rev.decache ()
        for filename, filerev, prevrev in hist['files']:
            revfile = rev.add_file (filename, filerev, prevrev)
            revfile.decache ()
        pulse.db.flush()

    revision = pulse.db.Revision.get_last_revision (branch=branch)
    if revision != None:
        branch.mod_datetime = revision.datetime
        branch.mod_person = revision.person


def process_maintainers (branch, checkout, **kw):
    maintfile = os.path.join (checkout.directory, 'MAINTAINERS')
    if not os.path.isfile (maintfile):
        return

    rel_scm = pulse.utils.relative_path (maintfile, pulse.config.scm_dir)
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
        line = pulse.utils.utf8dec (l.rstrip())
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
        ident = u'/person/%s@%s' % (userid, serverid)
        person = pulse.db.Entity.get_or_create (ident, u'Person')
        person.update (name=name)
        if email != None:
            person.email = email
        rel = pulse.db.ModuleEntity.set_related (branch, person, maintainer=True)
        rels.append (rel)
    branch.set_relations (pulse.db.ModuleEntity, rels)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)


def process_configure (branch, checkout, **kw):
    filename = os.path.join (checkout.directory, 'configure.in')
    if not os.path.exists (filename):
        filename = os.path.join (checkout.directory, 'configure.ac')
    if not os.path.exists (filename):
        return

    rel_scm = pulse.utils.relative_path (filename, pulse.config.scm_dir)
    mtime = os.stat(filename).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            return
    pulse.utils.log ('Processing file %s' % rel_scm)

    owd = os.getcwd ()
    try:
        os.chdir (checkout.directory)
        (status, output) = commands.getstatusoutput ('autoconf "%s" 2>/dev/null' % filename)
    finally:
        os.chdir (owd)
    if status != 256:
        output = open(filename).read()
    vars = {}
    functxts = {}
    infunc = None
    ac_inittxt = None
    am_inittxt = None
    varre = re.compile ('^([A-Z_]+)=\'?([^\']*)\'?')
    for line in output.split('\n'):
        if infunc == None:
            if line.startswith ('AC_INIT('):
                infunc = 'AC_INIT'
                functxts[infunc] = ''
                line = line[8:]
            elif line.startswith ('AM_INIT_AUTOMAKE('):
                infunc = 'AM_INIT_AUTOMAKE'
                functxts[infunc] = ''
                line = line[17:]
            elif line.startswith ('AS_VERSION('):
                infunc = 'AS_VERSION'
                functxts[infunc] = ''
                line = line[11:]
            else:
                m = varre.match (line)
                if m:
                    varval = m.group(2).strip()
                    if len(varval) > 0 and varval[0] == varval[-1] == '"':
                        varval = varval[1:-1]
                    vars[m.group(1)] = varval
        if infunc != None:
            rparen = line.find (')')
            if rparen >= 0:
                functxts[infunc] += line[:rparen]
                infunc = None
            else:
                functxts[infunc] += line.strip()

    initargs = functxts.get('AC_INIT', '').split(',')
    if len(initargs) < 2:
        initargs = functxts.get('AM_INIT_AUTOMAKE', '').split(',')
    if len(initargs) < 2:
        initargs = ['', '']
    for i in range(len(initargs)):
        arg = initargs[i]
        arg = arg.strip()
        if len(arg) > 0 and arg[0] == '[' and arg[-1] == ']':
            arg = arg[1:-1]
        arg = arg.strip()
        initargs[i] = arg
    if functxts.has_key ('AS_VERSION'):
        versargs = functxts['AS_VERSION'].split(',')
        initargs[0] = versargs[0].strip()
        initargs[1] = '.'.join ([s.strip() for s in versargs[2:5]])

    def subvar (var):
        r1 = re.compile ('(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)')
        r2 = re.compile ('\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?')
        ret = ''
        for el in r1.split(var):
            m = r2.match(el)
            if m and vars.has_key (m.group(1)):
                ret += subvar (vars[m.group(1)])
            else:
                ret += el
        return ret

    tarname = vars.get ('PACKAGE_TARNAME', '').strip()
    if tarname == '':
        tarname = vars.get ('PACKAGE_NAME', '').strip()
    if tarname == '':
        if len(initargs) >= 4:
            tarname = initargs[3]
        else:
            tarname = initargs[0]
    tarname = subvar (tarname)

    tarversion = vars.get ('PACKAGE_VERSION', '').strip()
    if tarversion == '':
        tarversion = initargs[1]
    tarversion = subvar (tarversion)

    series = tarversion.split('.')[:2]
    try:
        minor = int (series[1])
        if minor % 2 == 1:
            minor += 1
        series[1] = str (minor)
    except:
        pass
    series = '.'.join (series)

    branch.data['PACKAGE_NAME'] = vars.get ('PACKAGE_NAME', '').strip()
    branch.data['tarname'] = tarname
    branch.data['tarversion'] = tarversion
    branch.data['series'] = series

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)


def process_podir (branch, checkout, podir, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    ident = u'/'.join(['/i18n', bserver, bmodule, os.path.basename (podir), bbranch])
    domain = pulse.db.Branch.get_or_create (ident, u'Domain')
    domain.parent = branch

    scmdata = {}
    for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
        scmdata[key] = getattr(branch, key)
    scmdata['scm_dir'] = pulse.utils.relative_path (podir, checkout.directory)
    domain.update (scmdata)

    linguas = os.path.join (podir, 'LINGUAS')
    if not os.path.isfile (linguas):
        return domain

    rel_scm = pulse.utils.relative_path (linguas, pulse.config.scm_dir)
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
        lident = u'/l10n/' + lang + domain.ident
        translation = pulse.db.Branch.get_or_create (lident, u'Translation')
        translations.append (translation)
        ldata = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            ldata[key] = scmdata[key]
        ldata['subtype'] = 'intltool'
        ldata['scm_dir'] = scmdata['scm_dir']
        ldata['scm_file'] = lang + '.po'
        translation.update (ldata)
    domain.set_children (u'Translation', translations)

    if kw.get('do_i18n', True):
        for po in translations:
            pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return domain


def process_gdu_docdir (branch, checkout, docdir, makefile, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    doc_module = makefile['DOC_MODULE']
    if doc_module == '@PACKAGE_NAME@':
        doc_module = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
    ident = u'/'.join(['/doc', bserver, bmodule, doc_module, bbranch])
    document = pulse.db.Branch.get_or_create (ident, u'Document')
    document.parent = branch

    relpath = pulse.utils.relative_path (docdir, checkout.directory)

    data = {}
    for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
        data[key] = getattr(branch, key)
    data['subtype'] = u'gdu-docbook'
    data['scm_dir'] = os.path.join (relpath, 'C')
    data['scm_file'] = doc_module + '.xml'
    document.update (data)

    translations = []
    if makefile.has_key ('DOC_LINGUAS'):
        for lang in makefile['DOC_LINGUAS'].split():
            lident = u'/l10n/' + lang + document.ident
            translation = pulse.db.Branch.get_or_create (lident, u'Translation')
            translations.append (translation)
            ldata = {}
            for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                ldata[key] = data[key]
            ldata['subtype'] = u'xml2po'
            ldata['scm_dir'] = os.path.join (pulse.utils.relative_path (docdir, checkout.directory), lang)
            ldata['scm_file'] = lang + '.po'
            translation.update (ldata)
        document.set_children (u'Translation', translations)

    if kw.get('do_i18n', True):
        for po in translations:
            pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

    return document


def process_gtk_docdir (branch, checkout, docdir, makefile, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    doc_module = makefile['DOC_MODULE']
    ident = u'/'.join(['/ref', bserver, bmodule, doc_module, bbranch])
    document = pulse.db.Branch.get_or_create (ident, u'Document')
    relpath = pulse.utils.relative_path (docdir, checkout.directory)

    data = {}
    for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
        data[key] = getattr(branch, key)
    data['subtype'] = u'gtk-doc'
    data['scm_dir'] = relpath
    scm_file = makefile['DOC_MAIN_SGML_FILE']
    if '$(DOC_MODULE)' in scm_file:
        scm_file = scm_file.replace ('$(DOC_MODULE)', doc_module)
    data['scm_file'] = scm_file

    document.update (data)

    return document


def process_pkgconfig (branch, checkout, filename, **kw):
    basename = os.path.basename (filename)[:-6]
    rel_ch = pulse.utils.relative_path (filename, checkout.directory)
    rel_scm = pulse.utils.relative_path (filename, pulse.config.scm_dir)
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
            libs = pulse.db.Branch.select (type=u'Library', **data)
            try:
                return libs.one ()
            except:
                return None
    pulse.utils.log ('Processing file %s' % rel_scm)

    libname = ''
    libdesc = ''
    for line in open (filename):
        if line.startswith ('Name:'):
            libname = line[5:].strip()
        elif line.startswith ('Description:'):
            libdesc = line[12:].strip()
    if libname == '':
        return None

    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    ident = u'/'.join(['/lib', bserver, bmodule, basename, bbranch])
    lib = pulse.db.Branch.get_or_create (ident, u'Library')

    if libname == '@PACKAGE_NAME@':
        libname = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')

    lib.update (name=libname, desc=libdesc)

    docident = u'/'.join(['/ref', bserver, bmodule, basename, bbranch])
    doc = pulse.db.Branch.get (docident)
    if doc == None:
        match = re.match ('(.+)-\\d+(\\d\\d+)?', basename)
        if match:
            docident = u'/'.join(['/ref', bserver, bmodule, match.group(1), bbranch])
            doc = pulse.db.Branch.get (docident)
    if doc != None:
        rel = pulse.db.Documentation.set_related (lib, doc)
        lib.set_relations (pulse.db.Documentation, [rel])

    data = {}
    for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
        data[key] = getattr(branch, key)
    data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)

    lib.update (data)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return lib


def process_keyfile (branch, checkout, filename, **kw):
    rel_ch = pulse.utils.relative_path (filename, checkout.directory)
    rel_scm = pulse.utils.relative_path (filename, pulse.config.scm_dir)
    mtime = os.stat(filename).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            data = {'parent' : branch}
            data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
            apps = pulse.db.Branch.select (type=u'Application', **data)
            try:
                return apps.one ()
            except:
                return None
    pulse.utils.log ('Processing file %s' % rel_scm)
                     
    if filename.endswith ('.desktop.in.in'):
        basename = os.path.basename (filename)[:-14]
    else:
        basename = os.path.basename (filename)[:-11]
    owd = os.getcwd ()
    try:
        try:
            os.chdir (checkout.directory)
            keyfile = pulse.parsers.KeyFile (os.popen ('LC_ALL=C intltool-merge -d -q -u po "' + rel_ch + '" -'))
        finally:
            os.chdir (owd)
    except:
        return None
    if not keyfile.has_group ('Desktop Entry'):
        return None
    if not keyfile.has_key ('Desktop Entry', 'Type'):
        return None
    if keyfile.get_value ('Desktop Entry', 'Type') != 'Application':
        return None

    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    ident = u'/'.join(['/app', bserver, bmodule, basename, bbranch])

    name = keyfile.get_value ('Desktop Entry', 'Name')
    if isinstance (name, basestring):
        name = {'C' : name}

    if keyfile.has_key ('Desktop Entry', 'Comment'):
        desc = keyfile.get_value ('Desktop Entry', 'Comment')
        if isinstance (desc, basestring):
            desc = {'C' : desc}
    else:
        desc = None

    type = u'Application'
    if keyfile.has_key ('Desktop Entry', 'Categories'):
        cats = keyfile.get_value ('Desktop Entry', 'Categories')
        if 'Settings' in cats.split(';'):
            ident = u'/'.join(['/capplet', bserver, bmodule, basename, bbranch])
            type = u'Capplet'

    app = pulse.db.Branch.get_or_create (ident, type)

    data = {'data': {}}
    for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
        data[key] = getattr(branch, key)
    data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)

    app.update (name=name)
    if desc != None:
        app.update (desc=desc)
    if keyfile.has_key ('Desktop Entry', 'Icon'):
        iconname = keyfile.get_value ('Desktop Entry', 'Icon')
        if iconname == '@PACKAGE_NAME@':
            iconname = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
        locate_icon (app, iconname, kw.get ('images', []))

    if keyfile.has_key ('Desktop Entry', 'Exec'):
        data['data']['exec'] = keyfile.get_value ('Desktop Entry', 'Exec')
        if data['data']['exec'] == '@PACKAGE_NAME@':
            data['data']['exec'] = branch.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')

    app.update (data)

    if keyfile.has_key ('Desktop Entry', 'X-GNOME-DocPath'):
        docid = keyfile.get_value ('Desktop Entry', 'X-GNOME-DocPath')
        docid = docid.split('/')[0]
    else:
        docid = basename

    if docid != '':
        docident = u'/'.join(['/doc', bserver, bmodule, docid, bbranch])
        doc = pulse.db.Branch.get (docident)
        if doc != None:
            rel = pulse.db.Documentation.set_related (app, doc)
            app.set_relations (pulse.db.Documentation, [rel])

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return app


def process_oafserver (branch, checkout, filename, **kw):
    bserver, bmodule, bbranch = branch.ident.split('/')[2:]
    basename = os.path.basename (filename)[:-13]
    rel_ch = pulse.utils.relative_path (filename, checkout.directory)
    rel_scm = pulse.utils.relative_path (filename, pulse.config.scm_dir)
    mtime = os.stat(filename).st_mtime

    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.log ('Skipping file %s' % rel_scm)
            data = {'parent' : branch}
            data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
            applets = pulse.db.Branch.select (type=u'Applet', **data)
            return list(applets)
    pulse.utils.log ('Processing file %s' % rel_scm)

    owd = os.getcwd ()
    applets = []
    pulse.utils.log ('Processing file %s' %
                     pulse.utils.relative_path (filename, pulse.config.scm_dir))
    try:
        os.chdir (checkout.directory)
        dom = xml.dom.minidom.parse (
            os.popen ('LC_ALL=C intltool-merge -x -q -u po "' + rel_ch + '" - 2>/dev/null'))
    except:
        pulse.utils.warn ('Could not process file %s' %
                          pulse.utils.relative_path (filename, pulse.config.scm_dir))
        os.chdir (owd)
        return []
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
        applet = pulse.db.Branch.get_or_create (ident, u'Applet')
        applet.update (name=applet_name, desc=applet_desc)
        if applet_icon != None:
            locate_icon (applet, applet_icon, kw.get ('images', []))

        data = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            data[key] = getattr(branch, key)
        data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
        applet.update (data)
        applets.append (applet)

    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)

    return applets


def locate_icon (record, icon, images):
    icondir = os.path.join (pulse.config.web_icons_dir, 'apps')

    if icon.endswith ('.png'):
        iconfile = icon
        icon = icon[:-4]
    else:
        iconfile = icon + '.png'
    candidates = []
    for img in images:
        base = os.path.basename (img)
        if os.path.basename (img) == iconfile:
            candidates.append (img)
        elif base.startswith (icon) and base.endswith ('.png'):
            mid = base[len(icon):-4]
            if re.match ('[\.-]\d\d$', mid):
                candidates.append (img)
        elif base.startswith ('hicolor_apps_') and base.endswith (iconfile):
            candidates.append (img)
    use = None
    img22 = None
    img24 = None
    imgbig = None
    dimbig = None
    for img in candidates:
        im = Image.open (img)
        w, h = im.size
        if w == h == 24:
            img24 = img
            break
        elif w == h == 22:
            img22 = img
        elif w == h and w > 24:
            if dimbig == None or w < dimbig:
                imgbig = img
                dimbig = w
    use = img24 or img22
    if use != None:
        if not os.path.isdir (icondir):
            os.makedirs (icondir)
        shutil.copyfile (use, os.path.join (icondir, os.path.basename (use)))
        record.update ({'icon_dir' : 'apps', 'icon_name' : os.path.basename (use[:-4])})
    elif imgbig != None:
        if not os.path.isdir (icondir):
            os.makedirs (icondir)
        im = Image.open (imgbig)
        im.thumbnail((24, 24), Image.ANTIALIAS)
        im.save (os.path.join (icondir, os.path.basename (imgbig)), 'PNG')
        record.update ({'icon_dir' : 'apps', 'icon_name' : os.path.basename (imgbig[:-4])})
    elif record.icon_name == None or record.icon_name != icon:
        record.update (icon_dir='__icon__:apps', icon_name=icon)


def main (argv, options={}):
    update = not options.get ('--no-update', False)
    timestamps = not options.get ('--no-timestamps', False)
    history = not options.get ('--no-history', False)
    do_docs = not options.get ('--no-docs', False)
    do_i18n = not options.get ('--no-i18n', False)
    if len(argv) == 0:
        ident = None
    else:
        ident = pulse.utils.utf8dec (argv[0])

    if ident != None:
        if ident[:5] == u'/set/':
            branches = pulse.db.Branch.select (pulse.db.Branch.type == u'Module',
                                               pulse.db.Branch.ident == pulse.db.SetModule.pred_ident,
                                               pulse.db.SetModule.subj_ident.like (ident))
        else:
            branches = pulse.db.Branch.select (pulse.db.Branch.type == u'Module',
                                               pulse.db.Branch.ident.like (ident))
    else:
        branches = pulse.db.Branch.select (pulse.db.Branch.type == u'Module')

    for branch in list(branches):
        try:
            update_branch (branch, update=update, timestamps=timestamps, history=history,
                           do_docs=do_docs, do_i18n=do_i18n)
            pulse.db.flush ()
        except:
            pulse.db.rollback ()
            raise
        else:
            pulse.db.commit ()

    return 0
