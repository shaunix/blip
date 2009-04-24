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

        page = html.Page (module)
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

        tabs = []
        tabs = [app for app in self.applications if isinstance (app, applications.TabProvider)]
        for tab in utils.attrsorted (tabs, 'tab_group', 'application_id'):
            page.add_tab (tab.application_id, tab.get_tab_title ())
            if tab.tab_group == applications.TabProvider.FIRST_TAB:
                page.add_to_tab (tab.application_id, tab.get_tab())

        return


        # FIXME below
        page.add_tab ('info', utils.gettext ('Info'))
        box = html.Div()
        page.add_to_tab ('info', box)

        # Developers
        box = get_developers_box (module)
        page.add_sidebar_content (box)

        page.add_tab ('activity', utils.gettext ('Activity'))
        page.add_tab ('components', utils.gettext ('Components'))
        if module.select_children (u'Domain').count() > 0:
            page.add_tab ('translations', utils.gettext ('Translations'))

        # Dependencies
        deps = db.ModuleDependency.get_related (subj=module)
        deps = utils.attrsorted (list(deps), ['pred', 'scm_module'])
        if len(deps) > 0:
            box = html.SidebarBox (utils.gettext ('Dependencies'))
            page.add_sidebar_content (box)
            d1 = html.Div()
            d2 = html.Div()
            box.add_content (d1)
            box.add_content (html.Rule())
            box.add_content (d2)
            for dep in deps:
                div = html.Div ()
                link = html.Link (dep.pred.pulse_url, dep.pred.scm_module)
                div.add_content (link)
                if dep.direct:
                    d1.add_content (div)
                else:
                    d2.add_content (div)


def get_request_handler (request, response):
    return ModuleHandler (request, response)



def main (response, path, query):
    kw = {'path' : path, 'query' : query}
    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, branch, **kw)
    elif query.get('ajax', None) == 'domain':
        output_ajax_domain (response, branch, **kw)
    elif query.get('ajax', None) == 'revfiles':
        output_ajax_revfiles (response, branch, **kw)
    else:
        pass
        #output_module (response, branch, **kw)

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




def output_ajax_tab (response, module, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'components':
        response.set_contents (get_components_tab (module, **kw))
    elif tab == 'translations':
        response.set_contents (get_translations_tab (module, **kw))


def output_ajax_revfiles (response, module, **kw):
    if module.scm_server.endswith ('/svn/'):
        base = module.scm_server[:-4] + 'viewvc/'
        colon = base.find (':')
        if colon < 0:
            response.http_status = 404
            return
        if base[:colon] != 'http':
            base = 'http' + base[colon:]
        if module.scm_path != None:
            base += module.scm_path
        elif module.scm_branch == 'trunk':
            base += module.scm_module + '/trunk/'
        else:
            base += module.scm_module + '/branches/' + module.scm_branch + '/'

    query = kw.get ('query', {})
    revid = query.get('revid', None)
    revision = db.Revision.get (revid)
    files = db.RevisionFile.select (revision=revision)

    mlink = html.MenuLink (revision.revision, menu_only=True)
    response.set_contents (mlink)
    for file in files:
        url = base + file.filename
        url += '?r1=%s&r2=%s' % (file.prevrev, file.filerev)
        mlink.add_link (url, file.filename)








def get_developers_box (module):
    box = html.SidebarBox (title=utils.gettext ('Developers'))
    rels = db.ModuleEntity.get_related (subj=module)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
        for person in utils.attrsorted (people.keys(), 'title'):
            lbox = box.add_link_box (person)
            rel = people[person]
            if rel.maintainer:
                lbox.add_badge ('maintainer')
    else:
        box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                        utils.gettext ('No developers') ))
    return box


