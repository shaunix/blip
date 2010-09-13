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

import blinq.config
import blinq.utils

import blip.db
import blip.html
import blip.utils
import blip.web

class HomeHeaderLinks (blip.html.HeaderLinksProvider):
    @classmethod
    def add_header_links (cls, page, request):
        if request.account is not None:
            page.add_header_link (blinq.config.web_root_url + 'home',
                                  blip.utils.gettext ('Home'))

class HomePageResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if (len(request.path) == 1 and request.path[0] == 'home' and
            request.account is not None):
            return True
        return False

    @classmethod
    def respond (cls, request):
        if len(request.path) != 1 or request.path[0] != 'home' or request.account is None:
            return None

        response = blip.web.WebResponse (request)

        page = blip.html.Page (request=request)
        page.set_title (request.account.person.name)
        response.payload = page
        return response

class HomeTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) != 1 or request.path[0] != 'home':
            return
        if request.account is None:
            return
        page.add_tab ('home',
                      blip.utils.gettext ('Home'),
                      blip.html.TabProvider.FIRST_TAB)
        page.add_to_tab ('home', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox ()

        facts = blip.html.FactsTable ()
        tab.add_content (facts)

        facts.start_fact_group ()
        if request.account.person.name is not None:
            facts.add_fact (blip.utils.gettext ('Name'), request.account.person.title)

        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) != 1 or request.path[0] != 'home':
            return None
        if request.account is None:
            return None
        if not blip.html.TabProvider.match_tab (request, 'home'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
        return response

class WatchesTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) != 1 or request.path[0] != 'home':
            return
        if request.account is None:
            return
        cnt = blip.db.AccountWatch.select (username=request.account.username)
        cnt = cnt.count ()
        if cnt > 0:
            page.add_tab ('watch',
                          blip.utils.gettext ('Watches (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) != 1 or request.path[0] != 'home':
            return None
        if request.account is None:
            return None
        if not blip.html.TabProvider.match_tab (request, 'watch'):
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.ContainerBox ()
        response.payload = tab

        records = []
        for watch in blip.db.AccountWatch.select (username=request.account.username):
            watchreq = blip.web.WebRequest (http=False,
                                            path_info=watch.ident,
                                            query_string='')
            for loc in blip.web.RecordLocator.get_extensions ():
                if loc.locate_record (watchreq):
                    if watchreq.record is not None:
                        records.append (watchreq.record)
                    break
        for record in blinq.utils.attrsorted (records, 'title'):
            tab.add_link_box (record)

        return response
