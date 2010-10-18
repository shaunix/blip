# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

"""Output information about projects"""

import blinq.utils

import blip.db
import blip.html
import blip.utils

import blip.plugins.index.web

################################################################################
## Pages

class BranchResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) not in (3, 4) or request.path[0] != 'mod':
            return False
        ident = u'/' + u'/'.join(request.path)
        if len(request.path) == 3:
            branches = list(blip.db.Branch.select (project_ident=ident))
            if len(branches) == 0:
                return True
            branch = [branch for branch in branches if branch.is_default]
            if len(branch) == 0:
                return True
            request.record = branch[0]
        else:
            branch = blip.db.Branch.get (ident)
            if branch is None:
                return True
            request.record = branch
            branches = list(blip.db.Branch.select (project_ident=branch.project_ident))
        request.set_data ('branches', branches)
        return True

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) not in (3, 4) or request.path[0] != 'mod':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        branches = request.get_data ('branches', [])
        page = blip.html.Page (request=request)
        response.payload = page

        if len(branches) > 1:
            for branch in blinq.utils.attrsorted (branches, '-is_default', 'scm_branch'):
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
                      blip.utils.gettext ('Overview'),
                      blip.html.TabProvider.FIRST_TAB)
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox()

        for err in blip.db.Error.select (ident=request.record.ident):
            tab.add_content (blip.html.AdmonBox (blip.html.AdmonBox.error, err.message))

        facts = blip.html.FactsTable()
        tab.add_content (facts)

        facts.start_fact_group ()
        facts.add_fact (blip.utils.gettext ('Module Name'), request.record.title)
        if request.record.desc not in (None, ''):
            facts.add_fact (blip.utils.gettext ('Description'),
                            request.record.desc)

        sel = blip.db.Selection (blip.db.SetModule,
                                 blip.db.SetModule.pred_ident == request.record.ident)
        blip.db.SetModule.select_subj (sel)
        rels = sel.get_sorted (('[subj]', 'title'))
        if len(rels) > 0:
            span = blip.html.Span (*[blip.html.Link(rel['subj']) for rel in rels])
            span.set_divider (blip.html.BULLET)
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Release Sets'), span)

        facts.start_fact_group ()
        checkout = blip.scm.Repository.from_record (request.record, checkout=False, update=False)
        facts.add_fact (blip.utils.gettext ('Module'), request.record.scm_module)
        facts.add_fact (blip.utils.gettext ('Branch'), request.record.scm_branch)
        facts.add_fact (blip.utils.gettext ('Location'), checkout.location)

        if request.record.mod_datetime is not None:
            facts.start_fact_group ()
            if request.record.mod_person_ident is not None:
                facts.add_fact (blip.utils.gettext ('Modified'),
                                blip.html.Link (request.record.mod_person))
                facts.add_fact ('',
                                request.record.mod_datetime.strftime('%Y-%m-%d %T'))
            else:
                facts.add_fact (blip.utils.gettext ('Modified'),
                                request.record.mod_datetime.strftime('%Y-%m-%d %T'))

        if request.record.data.has_key ('pkgname'):
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Package'), request.record.data['pkgname'])
        if request.record.data.has_key ('pkgversion'):
            if not request.record.data.has_key ('pkgname'):
                facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Version'), request.record.data['pkgversion'])

        facts.start_fact_group ()
        span = blip.html.Span (divider=blip.html.SPACE)
        span.add_content (str(request.record.project.score))
        lt = blip.db.Project.select (blip.db.Project.type == u'Module',
                                     blip.db.Project.score != 0,
                                     blip.db.Project.score <= request.record.project.score)
        lt = lt.count()
        gt = blip.db.Project.select (blip.db.Project.type == u'Module',
                                     blip.db.Project.score > request.record.project.score)
        gt = gt.count()
        if (lt + gt) > 0:
            span.add_content ('(%.2f%%)' % ((100.0 * lt) / (lt + gt)))
        facts.add_fact (blip.utils.gettext ('Score'), span)

        sel = blip.db.Selection (blip.db.BranchForum,
                                 blip.db.BranchForum.subj_ident == request.record.ident)
        blip.db.BranchForum.select_pred (sel)
        sel = sel.get_sorted (('pred', 'title'))
        if len(sel) > 0:
            facts.start_fact_group()
            div = blip.html.Div()
            for rel in sel:
                div.add_content (blip.html.Div (blip.html.Link (rel['pred'])))
            facts.add_fact (blip.utils.gettext ('Mailing Lists'), div)

        if request.record.bug_database is not None:
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Bug Tracker'), 
                            blip.html.Link ( request.record.bug_database,
                                             request.record.bug_database))

        facts.start_fact_group ()
        span = blip.html.Span (divider=blip.html.BULLET)
        store = blip.db.get_store (blip.db.Entity)
        using = store.using (blip.db.Entity,
                             blip.db.Join (blip.db.Revision,
                                           blip.db.Revision.person_ident == blip.db.Entity.ident))
        cnt = blip.db.Count (blip.db.Revision.ident)
        sel = using.find (blip.db.Entity, blip.db.Revision.project_ident == request.record.project_ident)
        sel = sel.group_by (blip.db.Entity.ident)
        sel = sel.order_by (blip.db.Desc (cnt))
        for ent in sel[:10]:
            span.add_content (blip.html.Link (ent))
        facts.add_fact (blip.utils.gettext ('Top Committers'), span)

        if request.record.updated is not None:
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Last Updated'),
                            request.record.updated.strftime('%Y-%m-%d %T'))

        # Dependencies
        # deps = db.ModuleDependency.get_related (subj=self.handler.record)
        # deps = blinq.utils.attrsorted (list(deps), ['pred', 'scm_module'])
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

        response.payload = cls.get_tab (request)
        return response

class DevelopersTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'mod':
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                request.record.type == u'Module'):
            return None
        cnt = blip.db.ModuleEntity.count_related (subj=request.record)
        if cnt > 0:
            page.add_tab ('developers',
                          blip.utils.gettext ('Developers (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'mod':
            return None
        if not blip.html.TabProvider.match_tab (request, 'developers'):
            return None

        response = blip.web.WebResponse (request)

        tab = blip.html.ContainerBox ()

        rels = blip.db.ModuleEntity.select_related (subj=request.record)
        rels = blinq.utils.attrsorted (list(rels), '-maintainer', ('pred', 'title'))
        for rel in rels:
            lbox = tab.add_link_box (rel.pred)
            if rel.maintainer:
                lbox.add_badge ('maintainer')

        response.payload = tab
        return response

################################################################################
## Index Content

class SetIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response, **kw):
        """Construct an info box for the index page"""
        box = blip.html.SectionBox (blip.utils.gettext ('Modules'))
        page.add_content (box)

        txt = (blip.utils.gettext ('Blip is watching %i branches in %i projects.') %
               (blip.db.Branch.select (type=u'Module').count(),
                blip.db.Project.select (type=u'Module').count()))
        box.add_content (blip.html.Div (txt))

        columns = blip.html.ColumnBox (2)
        box.add_content (columns)

        sel = blip.db.Selection (blip.db.Project,
                                 blip.db.Project.type == u'Module',
                                 blip.db.Project.default != None)
        sel.add_join (blip.db.Branch,
                      blip.db.Branch.ident == blip.db.Project.default_ident)
        sel.add_result ('branch', blip.db.Branch)
        sel.order_by (blip.db.Desc (blip.db.Project.score))
        bl = blip.html.BulletList ()
        bl.set_title (blip.utils.gettext ('Active projects:'))
        columns.add_to_column (0, bl)
        for res in sel[:6]:
            bl.add_link (res['branch'].blip_url, res['branch'].title)

        sel = blip.db.Selection (blip.db.Project,
                                 blip.db.Project.type == u'Module',
                                 blip.db.Project.default != None)
        sel.add_join (blip.db.Branch,
                      blip.db.Branch.ident == blip.db.Project.default_ident)
        sel.add_result ('branch', blip.db.Branch)
        sel.order_by (blip.db.Desc (blip.db.Project.score_diff))
        bl = blip.html.BulletList ()
        bl.set_title (blip.utils.gettext ('Recently active:'))
        columns.add_to_column (1, bl)
        for res in sel[:6]:
            bl.add_link (res['branch'].blip_url, res['branch'].title)
