# Copyright (c) 2006-2008  Shaun McCance  <shaunm@gnome.org>
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

import datetime
import math
import re
import urllib

from pulse import applications, core, db, html, scm, utils

class ModuleHandler (core.RequestHandler):
    def initialize (self):
        ident = u'/' + u'/'.join(self.request.path)
        if len(self.request.path) == 3:
            branches = list(db.Branch.select (branchable=ident))
            if len(branches) == 0:
                raise core.RequestHandlerException (
                    utils.gettext ('Module Not Found'),
                    utils.gettext ('Pulse could not find the module %s')
                    % self.request.path[2])
            branch = [branch for branch in branches if branch.is_default]
            if len(branch) == 0:
                raise core.RequestHandlerException (
                    utils.gettext ('Default Branch Not Found'),
                    utils.gettext (
                    'Pulse could not find a default branch for the module %s')
                    % self.request.path[2])
            branch = branch[0]
        elif len(self.request.path) == 4:
            branch = db.Branch.get (ident)
            if branch is None:
                raise core.RequestHandlerException (
                    utils.gettext ('Branch Not Found'),
                    utils.gettext (
                    'Pulse could not find the branch %s of the module %s')
                    % (self.request.path[3], self.request.path[2]))
        else:
            raise core.RequestHandlerExcpeption (
                utils.gettext ('Branch Not Found'),
                utils.gettext ('Pulse could not find the branch %s') % ident)
        self.record = branch

    def handle_request (self):
        self.output_module_page ()

    def output_module_page (self):
        module = self.record
        branchable = module.branchable

        page = html.Page (self)
        self.response.set_contents (page)

        branches = utils.attrsorted (list(db.Branch.select (branchable=module.branchable)),
                                     '-is_default', 'scm_branch')
        if len(branches) > 1:
            for branch in branches:
                if branch.ident != module.ident:
                    page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
                else:
                    page.add_sublink (None, branch.ident.split('/')[-1])

        if module.data.has_key ('screenshot'):
            page.add_screenshot (module.data['screenshot'])


def get_request_handler (request, response):
    return ModuleHandler (request, response)


synopsis_sort = -1
def synopsis ():
    """Construct an info box for the front page"""
    box = html.SectionBox (utils.gettext ('Modules'))
    txt = (utils.gettext ('Pulse is watching %i branches in %i modules.') %
           (db.Branch.select (type=u'Module').count(),
            db.Branch.count_branchables (u'Module') ))
    box.add_content (html.Div (txt))

    columns = html.ColumnBox (2)
    box.add_content (columns)

    # FIXME STORM
    modules = db.Branch.select (type=u'Module').order_by (db.Desc (db.Branch.mod_score))
    bl = html.BulletList ()
    bl.set_title (utils.gettext ('Kicking ass and taking names:'))
    columns.add_to_column (0, bl)
    modules = modules[:6]
    scm_mods = {}
    for module in modules:
        scm_mods.setdefault (module.scm_module, 0)
        scm_mods[module.scm_module] += 1
    for module in modules:
        if scm_mods[module.scm_module] > 1:
            bl.add_link (module.pulse_url, module.branch_title)
        else:
            bl.add_link (module)

    modules = db.Branch.select (type=u'Module').order_by (db.Desc (db.Branch.mod_score_diff))
    bl = html.BulletList ()
    bl.set_title (utils.gettext ('Recently rocking:'))
    columns.add_to_column (1, bl)
    modules = modules[:6]
    scm_mods = {}
    for module in modules:
        scm_mods.setdefault (module.scm_module, 0)
        scm_mods[module.scm_module] += 1
    for module in modules:
        if scm_mods[module.scm_module] > 1:
            bl.add_link (module.pulse_url, module.branch_title)
        else:
            bl.add_link (module)
    return box

