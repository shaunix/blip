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

"""Output information about applications"""

import blinq.utils

import blip.db
import blip.html
import blip.utils

import blip.plugins.modules.web

class ApplicationResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) not in (4, 5) or request.path[0] != 'app':
            return False
        ident = u'/' + u'/'.join(request.path)
        if len(request.path) == 4:
            apps = list(blip.db.Branch.select (project_ident=ident))
            if len(apps) == 0:
                return True
            app = [app for app in apps if app.is_default]
            if len(app) == 0:
                return True
            request.record = app[0]
        else:
            app = blip.db.Branch.get (ident)
            if app is None:
                return True
            request.record = app
            apps = list(blip.db.Branch.select (project_ident=app.project_ident))
        request.set_data ('branches', apps)
        return True

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) not in (4, 5) or request.path[0] != 'app':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page

        page.add_trail_link (request.record.parent.blip_url,
                             request.record.parent.title)

        branches = request.get_data ('branches', [])
        if len(branches) > 1:
            for branch in blinq.utils.attrsorted (branches, '-is_default', 'scm_branch'):
                if branch.ident != request.record.ident:
                    page.add_sublink (branch.blip_url, branch.scm_branch)
                else:
                    page.add_sublink (None, branch.scm_branch)

        if request.record.data.has_key ('screenshot'):
            page.add_screenshot (request.record.data['screenshot'])

        return response

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'app':
            return None
        page.add_tab ('overview',
                      blip.utils.gettext ('Overview'),
                      blip.html.TabProvider.FIRST_TAB),
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox ()

        for err in blip.db.Error.select (ident=request.record.ident):
            tab.add_content (blip.html.AdmonBox (blip.html.AdmonBox.error, err.message))

        facts = blip.html.FactsTable ()
        tab.add_content (facts)

        facts.start_fact_group ()
        facts.add_fact (blip.utils.gettext ('Application'), request.record.title)
        if request.record.desc not in (None, ''):
            facts.add_fact (blip.utils.gettext ('Description'),
                            request.record.desc)

        sel = blip.db.Selection (blip.db.SetModule,
                                 blip.db.SetModule.pred_ident == request.record.parent_ident)
        blip.db.SetModule.select_subj (sel)
        rels = sel.get_sorted (('[subj]', 'title'))
        if len(rels) > 0:
            span = blip.html.Span (*[blip.html.Link(rel['subj']) for rel in rels])
            span.set_divider (blip.html.BULLET)
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Release Sets'), span)

        facts.start_fact_group ()
        checkout = blip.scm.Repository.from_record (request.record, checkout=False, update=False)
        facts.add_fact (blip.utils.gettext ('Module'),
                        blip.html.Link (request.record.parent.blip_url,
                                        request.record.scm_module))
        facts.add_fact (blip.utils.gettext ('Branch'), request.record.scm_branch)
        facts.add_fact (blip.utils.gettext ('Location'), checkout.location)

        if request.record.mod_datetime is not None:
            span = blip.html.Span(divider=blip.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            span.add_content (request.record.mod_datetime.strftime('%Y-%m-%d %T'))
            page.add_fact (pulse.utils.gettext ('Last Modified'), span)

        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'app':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
        return response

class ApplicationsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1:
            return None
        if request.record is None:
            return None
        if request.path[0] == 'mod':
            apps = blip.db.Branch.select (type=u'Application',
                                          parent=request.record)
        elif request.path[0] == 'set':
            apps = blip.db.Branch.select (type=u'Application',
                                          parent_in_set=request.record)
        else:
            return None
        cnt = apps.count ()
        if cnt > 0:
            page.add_tab ('apps',
                          blip.utils.gettext ('Applications (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if request.record is None:
            return None
        if not blip.html.TabProvider.match_tab (request, 'apps'):
            return None

        sel = blip.db.Selection (blip.db.Branch,
                                 blip.db.Branch.type == u'Application')
        if request.record.type == u'Module':
            sel.add_where (blip.db.Branch.parent_ident == request.record.ident)
        elif request.record.type == u'Set':
            sel.add_join (blip.db.SetModule,
                          blip.db.SetModule.pred_ident == blip.db.Branch.parent_ident)
            sel.add_where (blip.db.SetModule.subj_ident == request.record.ident)
            blip.db.Branch.select_parent (sel)
        else:
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.ContainerBox ()
        tab.set_columns (2)
        if request.record.type == u'Set':
            tab.add_sort_link ('title', blip.utils.gettext ('title'), 1)
            tab.add_sort_link ('module', blip.utils.gettext ('module'))

        for app in sel.get_sorted ('title'):
            lbox = tab.add_link_box (app)
            if request.record.type == u'Set':
                lbox.add_fact (blip.utils.gettext ('module'),
                               blip.html.Span(blip.html.Link (app['parent'].blip_url,
                                                              app['parent'].branch_module),
                                              html_class='module'))
                               

        response.payload = tab
        return response
