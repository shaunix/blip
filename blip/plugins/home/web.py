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

import datetime

import blinq.config
import blinq.utils

import blinq.ext

import blip.db
import blip.html
import blip.utils
import blip.web

import blip.plugins.index.web

class MessageFormatter (blinq.ext.ExtensionPoint):
    @classmethod
    def format_message (cls, message, record):
        return None

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
            page.add_tab ('messages',
                          blip.utils.gettext ('Messages'),
                          blip.html.TabProvider.CORE_TAB)
            page.add_tab ('watch',
                          blip.utils.gettext ('Watches (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def get_watched_records (cls, request):
        records = []
        for watch in blip.db.AccountWatch.select (username=request.account.username):
            watchreq = blip.web.WebRequest (http=False,
                                            path_info=watch.ident,
                                            query_string='')
            for loc in blip.web.RecordLocator.get_extensions ():
                if loc.locate_record (watchreq):
                    if watchreq.record is not None:
                        records.append ((watch.ident, watchreq.record))
                    break
        return blinq.utils.attrsorted (records, (1, 'title'))

    @classmethod
    def get_watch_tab (cls, request):
        tab = blip.html.ContainerBox ()
        for ident, record in cls.get_watched_records (request):
            tab.add_link_box (record)
        return tab

    @classmethod
    def get_messages_tab (cls, request):
        tab = blip.html.ActivityContainer ()
        idents = []
        records = {}
        for ident, record in cls.get_watched_records (request):
            idents.append (ident)
            records[ident] = record
        messages = blip.db.Message.select (blip.db.Message.subj.is_in (idents))
        messages = messages.order_by (blip.db.Desc (blip.db.Message.datetime))
        for message in messages[:100]:
            for formatter in MessageFormatter.get_extensions ():
                cont = formatter.format_message (message, records[message.subj])
                if cont is not None:
                    date = message.datetime.strftime ('%Y-%m-%d')
                    cont.set_datetime (None)
                    tab.add_activity (date, cont)
                    continue
        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) != 1 or request.path[0] != 'home':
            return None
        if request.account is None:
            return None

        if blip.html.TabProvider.match_tab (request, 'watch'):
            tab = cls.get_watch_tab (request)
        elif blip.html.TabProvider.match_tab (request, 'messages'):
            tab = cls.get_messages_tab (request)
        else:
            return None

        response = blip.web.WebResponse (request)
        response.payload = tab
        return response

class MessageIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response, **kw):
        """Construct an info box for the index page"""
        bl = blip.html.BulletList ()
        messages = blip.db.Message.select ()
        messages = messages.order_by (blip.db.Desc (blip.db.Message.datetime))
        idents = []
        lastdt = None
        for message in messages[:12]:
            if message.subj in idents:
                continue
            idents.append (message.subj)
            record = None
            req = blip.web.WebRequest (http=False,
                                       path_info=message.subj,
                                       query_string='')
            for loc in blip.web.RecordLocator.get_extensions ():
                if loc.locate_record (req):
                    if req.record is not None:
                        record = req.record
                    break
            if record is not None:
                bl.add_link (record)
                lastdt = message.datetime
        if lastdt is not None:
            diff = datetime.datetime.utcnow() - lastdt
            if diff.days > 0:
                box = blip.html.SidebarBox (blip.utils.gettext ('Last %i days') % diff.days)
            elif diff.seconds > 60:
                box = blip.html.SidebarBox (blip.utils.gettext ('Last %i minutes') % (diff.seconds // 60))
            else:
                box = blip.html.SidebarBox (blip.utils.gettext ('Last %i seconds') % diff.seconds)
        else:
            box = blip.html.SidebarBox (blip.utils.gettext ('Recent'))
        box.add_content (bl)
        page.add_sidebar_content (box)
