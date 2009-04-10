# Copyright (c) 2006-2009  Shaun McCance  <shaunm@gnome.org>
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

"""
ModuleScanner plugin for applications.
"""

import re
import os

from pulse import config, db, parsers, utils

import pulse.plugins.images
import pulse.pulsate.modules

class KeyFileHandler (object):
    """
    ModuleScanner plugin for applications.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.keyfiles = []
        self.appdocs = []
        self.appicons = []

    def process_file (self, dirname, basename, **kw):
        """
        Process a desktop entry file for an application.
        """
        if not re.match('.*\.desktop(\.in)+$', basename):
            return

        filename = os.path.join (dirname, basename)
        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]
        
        rel_ch = utils.relative_path (filename, checkout.directory)
        rel_scm = utils.relative_path (filename, config.scm_dir)
        mtime = os.stat(filename).st_mtime

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                data = {'parent' : branch}
                data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
                apps = db.Branch.select (type=u'Application', **data)
                try:
                    app = apps.one ()
                    self.scanner.add_child (app)
                    return
                except:
                    return
        utils.log ('Processing file %s' % rel_scm)
                     
        if filename.endswith ('.desktop.in.in'):
            basename = os.path.basename (filename)[:-14]
        else:
            basename = os.path.basename (filename)[:-11]
        owd = os.getcwd ()
        try:
            try:
                os.chdir (checkout.directory)
                keyfile = parsers.KeyFile (
                    os.popen ('LC_ALL=C intltool-merge -d -q -u po "' + rel_ch + '" -'))
            finally:
                os.chdir (owd)
        except:
            return
        if not keyfile.has_group ('Desktop Entry'):
            return
        if not keyfile.has_key ('Desktop Entry', 'Type'):
            return
        if keyfile.get_value ('Desktop Entry', 'Type') != 'Application':
            return

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

        apptype = u'Application'
        if keyfile.has_key ('Desktop Entry', 'Categories'):
            cats = keyfile.get_value ('Desktop Entry', 'Categories')
            if 'Settings' in cats.split(';'):
                ident = u'/'.join(['/capplet', bserver, bmodule, basename, bbranch])
                apptype = u'Capplet'

        app = db.Branch.get_or_create (ident, apptype)

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
            self.appicons.append ((app, iconname))

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
            self.appdocs.append ((app, docident))

        db.Timestamp.set_timestamp (rel_scm, mtime)
        if app is not None:
            self.scanner.add_child (app)

    def post_process (self, **kw):
        """
        Update other information about applications in a module.

        This function will locate documentation for applications.  This
        happens in post-processing to allow other plugins to add documents.

        This function will locate icons for applications.  This happens
        in post-processing to allow the images plugin to find all images.
        """
        images = self.scanner.get_plugin (pulse.plugins.images.ImagesHandler)
        for app, iconname in self.appicons:
            images.locate_icon (app, iconname)
        for app, docident in self.appdocs:
            doc = db.Branch.get (docident)
            if doc is not None:
                rel = db.Documentation.set_related (app, doc)
                if doc.data.has_key ('screenshot'):
                    app.data['screenshot'] = doc.data['screenshot']
                app.set_relations (db.Documentation, [rel])

pulse.pulsate.modules.ModuleScanner.register_plugin (KeyFileHandler)
