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
ModuleScanner plugin for panel applets.
"""

import os
import re
import xml

from pulse import config, db, utils

import pulse.plugins.images
import pulse.pulsate.modules

class OafServerHandler (object):
    """
    ModuleScanner plugin for panel applets.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.oafservers = []

    def process_file (self, dirname, basename, **kw):
        """
        Process an OAF server file for a panel applet.
        """
        if re.match('.*\.server(\.in)+$', basename):
            self.oafservers.append (os.path.join (dirname, basename))

    def update (self, **kw):
        """
        Update all panel applets for a module.
        """
        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]
        for filename in self.oafservers:
            rel_ch = utils.relative_path (filename, checkout.directory)
            rel_scm = utils.relative_path (filename, config.scm_dir)
            mtime = os.stat(filename).st_mtime

            if not kw.get('no_timestamps', False):
                stamp = db.Timestamp.get_timestamp (rel_scm)
                if mtime <= stamp:
                    utils.log ('Skipping file %s' % rel_scm)
                    data = {'parent' : branch}
                    data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
                    applets = db.Branch.select (type=u'Applet', **data)
                    for applet in applets:
                        self.scanner.add_child (applet)
                    continue
            utils.log ('Processing file %s' % rel_scm)

            owd = os.getcwd ()
            utils.log ('Processing file %s' %
                       utils.relative_path (filename, config.scm_dir))
            try:
                os.chdir (checkout.directory)
                dom = xml.dom.minidom.parse (
                    os.popen ('LC_ALL=C intltool-merge -x -q -u po "' + rel_ch + '" - 2>/dev/null'))
            except:
                utils.warn ('Could not process file %s' %
                            utils.relative_path (filename, config.scm_dir))
                os.chdir (owd)
                continue
            os.chdir (owd)
            for server in dom.getElementsByTagName ('oaf_server'):
                is_applet = False
                applet_name = {}
                applet_desc = {}
                applet_icon = None
                applet_iid = server.getAttribute ('iid')
                if applet_iid == '':
                    continue
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
                        if lang == '':
                            lang = 'C'
                        value = oafattr.getAttribute ('value')
                        if value != '':
                            applet_name[lang] = value
                    if oafattr.getAttribute ('name') == 'description':
                        lang = oafattr.getAttribute ('xml:lang')
                        if lang == '':
                            lang = 'C'
                        value = oafattr.getAttribute ('value')
                        if value != '':
                            applet_desc[lang] = value
                    if oafattr.getAttribute ('name') == 'panel:icon':
                        applet_icon = oafattr.getAttribute ('value')
                        if applet_icon == '':
                            applet_icon = None
                if not is_applet or applet_icon == None:
                    continue
                ident = '/'.join(['/applet', bserver, bmodule, applet_iid, bbranch])
                applet = db.Branch.get_or_create (ident, u'Applet')
                applet.update (name=applet_name, desc=applet_desc)
                if applet_icon != None:
                    images = self.scanner.get_plugin (pulse.plugins.images.ImagesHandler)
                    images.locate_icon (applet, applet_icon)

                data = {}
                for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                    data[key] = getattr(branch, key)
                data['scm_dir'], data['scm_file'] = os.path.split (rel_ch)
                applet.update (data)
                self.scanner.add_child (applet)

            db.Timestamp.set_timestamp (rel_scm, mtime)

pulse.pulsate.modules.ModuleScanner.register_plugin (OafServerHandler)
