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

"""Output information about release sets"""

import blinq.config
import blinq.utils

import blip.db
import blip.html
import blip.utils

import blip.plugins.index.web

################################################################################
## Pages

class AllSetsResponder (blip.web.PageResponder):
    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) != 1 or request.path[0] != 'set':
            return None

        response = blip.web.WebResponse (request)

        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext ('Sets'))
        cont = blip.html.ContainerBox ()
        cont.set_show_icons (False)
        cont.set_columns (2)
        page.add_content (cont)

        sets = blip.db.ReleaseSet.select (parent=None)
        sets = blinq.utils.attrsorted (list(sets), 'title')
        for rset in sets:
            lbox = cont.add_link_box (rset)
            subsets = blinq.utils.attrsorted (list(rset.subsets), ['title'])
            if len(subsets) > 0:
                bl = blip.html.BulletList ()
                lbox.add_content (bl)
                for subset in subsets:
                    bl.add_link (subset)
            else:
                SetResponder.add_set_info (rset, lbox)

        response.payload = page
        return response


class SetResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) < 2 or request.path[0] != 'set':
            return False
        ident = '/' + '/'.join(request.path)
        request.record = blip.db.ReleaseSet.get (ident)
        return True

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) != 2 or request.path[0] != 'set':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page

        page.add_trail_link (blinq.config.web_root_url + 'set', blip.utils.gettext ('Sets'))
        for superset in cls.get_supersets (request.record):
            page.add_trail_link (superset.blip_url, superset.title)

        # Schedule
        schedule = request.record.data.get ('schedule', [])
        if len(schedule) == 0 and request.record.parent != None:
            schedule = request.record.parent.data.get ('schedule', [])
        if len(schedule) > 0:
            box = blip.html.SectionBox (blip.utils.gettext ('Schedule'))
            cal = blip.html.Calendar ()
            box.add_content (cal)
            page.add_to_tab ('overview', box)
            for event in schedule:
                cal.add_event (*event)

        # Links
        links = request.record.data.get ('links', [])
        if len(links) == 0 and request.record.parent != None:
            links = request.record.parent.data.get ('links', [])
        if len(links) > 0:
            box = blip.html.InfoBox (blip.utils.gettext ('Links'))
            box.set_show_icons (False)
            page.add_to_tab ('overview', box)
            for link in links:
                lbox = box.add_link_box (link[0], link[1])
                lbox.set_description (link[2])

        return response

    @staticmethod
    def get_supersets (record):
        """Get a list of the supersets of a release set"""
        superset = record.parent
        if superset == None:
            return []
        else:
            supers = SetResponder.get_supersets (superset)
            return supers + [superset]

    @staticmethod
    def add_set_info (record, lbox):
        cnt = blip.db.SetModule.count_related (subj=record)
        if cnt > 0:
            bl = blip.html.BulletList ()
            lbox.add_content (bl)
            bl.add_link (record.blip_url, # + '#modules',
                         blip.utils.gettext ('%i modules') % cnt)
        else:
            return

        # Documents
        cnt = blip.db.Branch.select (type=u'Document', parent_in_set=record)
        cnt = cnt.count()
        if cnt > 0:
            bl.add_link (record.blip_url + '#docs',
                         blip.utils.gettext ('%i documents') % cnt)

        # Domains
        cnt = blip.db.Branch.select (type=u'Domain', parent_in_set=record)
        cnt = cnt.count()
        if cnt > 0:
            bl.add_link (record.blip_url + '#domains',
                         blip.utils.gettext ('%i domains') % cnt)

        # Programs
        objs = blip.db.Branch.select (
            blip.db.Branch.type.is_in ((u'Application', u'Capplet', u'Applet')),
            parent_in_set=record)
        cnt = objs.count()
        if cnt > 0:
            bl.add_link (record.blip_url + '#apps',
                         blip.utils.gettext ('%i applications') % cnt)

        # Libraries
        cnt = blip.db.Branch.select (type=u'Library', parent_in_set=record)
        cnt = cnt.count()
        if cnt > 0:
            bl.add_link (record.blip_url + '#libraries',
                         blip.utils.gettext ('%i libraries') % cnt)


################################################################################
## Tabs

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 2 or request.path[0] != 'set':
            return None
        cnt = request.record.subsets.count ()
        if cnt > 0:
            page.add_tab ('overview',
                          blip.utils.gettext ('Subsets (%i)' % cnt),
                          blip.html.TabProvider.FIRST_TAB)
        else:
            cnt = blip.db.SetModule.count_related (subj=request.record)
            page.add_tab ('overview',
                          blip.utils.gettext ('Modules (%i)' % cnt),
                          blip.html.TabProvider.FIRST_TAB)
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        subsets = blinq.utils.attrsorted (list(request.record.subsets), ['title'])
        if len(subsets) > 0:
            cont = blip.html.ContainerBox ()
            cont.set_show_icons (False)
            cont.set_columns (2)
            for subset in subsets:
                lbox = cont.add_link_box (subset)
                SetResponder.add_set_info (subset, lbox)
            return cont

        if request.record is None:
            cont = blip.html.AdmonBox (
                blip.html.AdmonBox.error,
                blip.utils.gettext ('Blip could not find the set %s')
                % '/'.join(request.path[1:]))
            response.payload = cont
            return response

        sel = blip.db.Selection (blip.db.Branch,
                                 blip.db.Branch.type == u'Module')
        sel.add_join (blip.db.SetModule,
                      blip.db.SetModule.pred_ident == blip.db.Branch.ident)
        sel.add_where (blip.db.SetModule.subj_ident == request.record.ident)
        blip.db.Branch.select_mod_person (sel)
        blip.db.Branch.select_project (sel)
        mods = sel.get_sorted ('title')
        modcnt = len(mods)
        cont = blip.html.ContainerBox (html_id='c-modules')
        cont.add_sort_link ('title', blip.utils.gettext ('title'), 1)
        cont.add_sort_link ('module', blip.utils.gettext ('module'))
        cont.add_sort_link ('mtime', blip.utils.gettext ('modified'))
        cont.add_sort_link ('score', blip.utils.gettext ('score'))
        for mod in mods:
            lbox = cont.add_link_box (mod)
            lbox.add_graph (blinq.config.web_files_url + 'graphs/' +
                            '/'.join(mod.ident.split('/')[1:] + ['commits-tight.png']),
                            width=208, height=40)
            span = blip.html.Span (mod.branch_module)
            span.add_html_class ('module')
            lbox.add_fact (blip.utils.gettext ('module'), blip.html.Link (mod.blip_url, span))
            if mod.mod_datetime is not None:
                span = blip.html.Span (divider=blip.html.SPACE)
                # FIXME: i18n, word order, but we want to link person
                span.add_content (blip.html.Span(mod.mod_datetime.strftime('%Y-%m-%d %T')))
                span.add_html_class ('mtime')
                if mod['mod_person'] is not None:
                    span.add_content (blip.utils.gettext ('by'))
                    span.add_content (blip.html.Link (mod['mod_person']))
                lbox.add_fact (blip.utils.gettext ('modified'), span)
            if mod['project'].score != None:
                span = blip.html.Span(str(mod['project'].score))
                span.add_html_class ('score')
                lbox.add_fact (blip.utils.gettext ('score'), span)
        return cont

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) < 1 or request.path[0] != 'set':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)
        response.payload = cls.get_tab (request)
        return response


################################################################################
## Index Content

class SetIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response, **kw):
        """Construct an info box for the index page"""
        box = blip.html.SidebarBox (blip.utils.gettext ('Sets'))
        bl = blip.html.BulletList ()
        box.add_content (bl)
        sets = blip.db.ReleaseSet.select (blip.db.ReleaseSet.parent_ident == None)
        sets = blinq.utils.attrsorted (list(sets), 'title')
        for rset in sets:
            bl.add_link (rset)
        page.add_sidebar_content (box)
