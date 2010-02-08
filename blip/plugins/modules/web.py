# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
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

"""Output information about projects"""

import blip.db
import blip.html
import blip.utils

import blip.plugins.index.web

################################################################################
## Pages

class BranchResponder (blip.web.PageResponder):
    @staticmethod
    def get_record_and_branches (request):
        ident = u'/' + u'/'.join(request.path)
        if len(request.path) == 3:
            branches = list(blip.db.Branch.select (project_ident=ident))
            if len(branches) == 0:
                raise blip.web.WebException (
                    blip.utils.gettext ('Project Not Found'),
                    blip.utils.gettext ('Blip could not find the project %s on %s')
                    % (request.path[2], request.path[1]))
            branch = [branch for branch in branches if branch.is_default]
            if len(branch) == 0:
                raise blip.web.WebException (
                    blip.utils.gettext ('Default Branch Not Found'),
                    blip.utils.gettext ('Blip could not find a default branch for the project %s on %s')
                    % (request.path[2], request.path[1]))
            request.record = branch[0]
        else:
            branch = blip.db.Branch.get (ident)
            if branch is None:
                raise blip.web.WebException (
                    blip.utils.gettext ('Branch Not Found'),
                    blip.utils.gettext ('Blip could not find the branch %s for the project %s on %s')
                    % (request.path[3], request.path[2], request.path[1]))
            request.record = branch
            branches = list(blip.db.Branch.select (project_ident=branch.project_ident))
        return branches

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) not in (3, 4):
            return None
        if request.path[0] != 'mod':
            return None

        response = blip.web.WebResponse (request)

        try:
            branches = cls.get_record_and_branches (request)
        except blip.web.WebException, err:
            page = blip.html.PageNotFound (err.desc, title=err.title)
            response.set_widget (page)
            return response

        page = blip.html.Page (request=request)
        response.set_widget (page)

        page.set_sublinks_divider (blip.html.BULLET)
        if len(branches) > 1:
            for branch in blip.utils.attrsorted (branches, '-is_default', 'scm_branch'):
                if branch.ident != request.record.ident:
                    page.add_sublink (branch.blip_url, branch.ident.split('/')[-1])
                else:
                    page.add_sublink (None, branch.ident.split('/')[-1])
        if request.record.data.has_key ('screenshot'):
            page.add_screenshot (request.record.data['screenshot'])

        return response


################################################################################
## Tabs

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'mod':
            return None
        page.add_tab ('overview',
                      blip.utils.gettext ('Overview'))
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox()

        if request.record.error != None:
            tab.add_content (blip.html.AdmonBox (blip.html.AdmonBox.error, request.record.error))

        facts = blip.html.FactsTable()
        tab.add_content (facts)

        sep = False
        try:
            facts.add_fact (utils.gettext ('Description'),
                            request.record.desc)
            sep = True
        except:
            pass

        rels = blip.db.SetModule.get_related (pred=request.record)
        if len(rels) > 0:
            sets = blip.utils.attrsorted ([rel.subj for rel in rels], 'title')
            span = blip.html.Span (*[blip.html.Link(rset) for rset in sets])
            span.set_divider (blip.html.BULLET)
            facts.add_fact (blip.utils.gettext ('Release Sets'), span)
            sep = True

        if sep:
            facts.add_fact_divider ()

        checkout = blip.scm.Repository.from_record (request.record, checkout=False, update=False)
        facts.add_fact (blip.utils.gettext ('Location'), checkout.location)

        if request.record.mod_datetime != None:
            span = blip.html.Span(divider=html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            span.add_content (request.record.mod_datetime.strftime('%Y-%m-%d %T'))
            if reqeust.record.mod_person_ident != None:
                span.add_content (' by ')
                span.add_content (blip.html.Link (request.record.mod_person))
            facts.add_fact (blip.utils.gettext ('Last Modified'), span)

        if request.record.data.has_key ('tarname'):
            facts.add_fact_divider ()
            facts.add_fact (blip.utils.gettext ('Tarball Name'), request.record.data['tarname'])
        if request.record.data.has_key ('tarversion'):
            if not request.record.data.has_key ('tarname'):
                facts.add_fact_divider ()
            facts.add_fact (blip.utils.gettext ('Version'), request.record.data['tarversion'])

        facts.add_fact_divider ()
        facts.add_fact (blip.utils.gettext ('Score'), str(request.record.mod_score))

        if request.record.bug_database is not None:
            facts.add_fact_divider ()
            facts.add_fact (blip.utils.gettext ('Bug Tracker'), 
                            blip.html.Link ( request.record.bug_database,
                                             request.record.bug_database))

        if request.record.updated is not None:
            facts.add_fact_divider ()
            facts.add_fact (blip.utils.gettext ('Last Updated'),
                            request.record.updated.strftime('%Y-%m-%d %T'))

        # Developers
        #box = self.get_developers_box ()
        #tab.add_content (box)

        # Dependencies
        # deps = db.ModuleDependency.get_related (subj=self.handler.record)
        # deps = utils.attrsorted (list(deps), ['pred', 'scm_module'])
        # if len(deps) > 0:
        #     box = html.ContainerBox (utils.gettext ('Dependencies'))
        #     tab.add_content (box)
        #     d1 = html.Div()
        #     d2 = html.Div()
        #     box.add_content (d1)
        #     box.add_content (html.Rule())
        #     box.add_content (d2)
        #     for dep in deps:
        #         depdiv = html.Div ()
        #         link = html.Link (dep.pred.pulse_url, dep.pred.scm_module)
        #         depdiv.add_content (link)
        #         if dep.direct:
        #             d1.add_content (depdiv)
        #         else:
        #             d2.add_content (depdiv)
        return tab

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) < 1 or request.path[0] != 'mod':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        try:
            branches = BranchResponder.get_record_and_branches (request)
        except blip.web.WebException, err:
            cont = blip.html.AdmonBox (blip.html.AdmonBox.error, err.desc)
            response.set_widget (cont)
            return response

        response.set_widget (cls.get_tab (request))
        return response


################################################################################
## Index Content

class SetIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response, **kw):
        """Construct an info box for the index page"""
        box = blip.html.SectionBox (blip.utils.gettext ('Modules'))
        page.add_content (box)

        txt = (blip.utils.gettext ('Pulse is watching %i branches in %i projects.') %
               (blip.db.Branch.select (type=u'Module').count(),
                blip.db.Project.select (type=u'Module').count()))
        box.add_content (blip.html.Div (txt))

        columns = blip.html.ColumnBox (2)
        box.add_content (columns)
        modules = blip.db.Branch.select (type=u'Module').order_by (blip.db.Desc (blip.db.Branch.mod_score))
        bl = blip.html.BulletList ()
        bl.set_title (blip.utils.gettext ('Active projects:'))
        columns.add_to_column (0, bl)
        modules = modules[:6]
        scm_mods = {}
        for module in modules:
            scm_mods.setdefault (module.scm_module, 0)
            scm_mods[module.scm_module] += 1
        for module in modules:
            if scm_mods[module.scm_module] > 1:
                bl.add_link (module.blip_url, module.branch_title)
            else:
                bl.add_link (module)

        modules = blip.db.Branch.select (type=u'Module').order_by (blip.db.Desc (blip.db.Branch.mod_score_diff))
        bl = blip.html.BulletList ()
        bl.set_title (blip.utils.gettext ('Recently active:'))
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
