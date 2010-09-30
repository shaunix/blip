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
import os

import blinq.config
import blinq.utils

import blip.db
import blip.html
import blip.utils
import blip.web

import blip.plugins.home.web
import blip.plugins.index.web

class ListsIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response):
        """Construct an info box for the index page"""
        mls = blip.db.Forum.select (type=u'List')

        if mls.count() == 0:
            return

        box = blip.html.SidebarBox (blip.utils.gettext ('Lists'))
        page.add_sidebar_content (box)

        #txt = (blip.utils.gettext ('Blip is watching %i mailing lists.') %
        #       blip.db.Forum.select (type=u'List').count() )
        #box.add_content (blip.html.Div (txt))

        active = mls.order_by (blip.db.Desc (blip.db.Forum.score))
        bl = blip.html.BulletList ()
        box.add_content (bl)
        for ml in active[:6]:
            bl.add_link (ml)

class ListReponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) != 3 or request.path[0] != 'list':
            return False
        ident = u'/' + u'/'.join(request.path)
        request.record = blip.db.Forum.get (ident)
        return True

    @classmethod
    def respond (cls, request):
        if len(request.path) != 3 or request.path[0] != 'list':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page
        return response

class ListPostsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if request.record is None:
            return
        if isinstance (request.record, blip.db.Forum) and request.record.type == u'List':
            cnt = blip.db.ForumPost.select (forum=request.record).count ()
        elif isinstance (request.record, blip.db.Entity):
            cnt = blip.db.ForumPost.select (author=request.record).count ()
        else:
            cnt = None
        if cnt is not None and cnt > 0:
            page.add_tab ('posts',
                          blip.utils.gettext ('Posts'),
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if not blip.html.TabProvider.match_tab (request, 'posts'):
            return None
        if isinstance (request.record, blip.db.Forum) and request.record.type == u'List':
            sel = (blip.db.ForumPost.forum == request.record)
        elif isinstance (request.record, blip.db.Entity):
            sel = (blip.db.ForumPost.author == request.record)
        else:
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.PaddingBox ()
        response.payload = tab
        graph = blip.html.BarGraph ()
        tab.add_content (graph)

        store = blip.db.get_store (blip.db.ForumPost)
        sel = store.find ((blip.db.ForumPost.weeknum, blip.db.Count('*')), sel)
        sel = sel.group_by (blip.db.ForumPost.weeknum)
        sel = sel.order_by (blip.db.ForumPost.weeknum)

        curweek = blip.utils.weeknum()
        lastweek = None
        for weeknum, count in sel:
            if weeknum is None:
                continue
            if weeknum > curweek:
                weeknum = lastweek
                break
            if lastweek is not None and weeknum > lastweek + 1:
                for i in range(weeknum - lastweek - 1):
                    graph.add_bar (0)
            lastweek = weeknum
            if weeknum == curweek:
                label = blip.utils.gettext ('this week')
            elif weeknum == curweek - 1:
                label = blip.utils.gettext ('last week')
            else:
                label = (blip.utils.gettext ('week of %s') %
                         blip.utils.weeknumday(weeknum).strftime('%Y-%m-%d'))
            link = blip.utils.gettext ('%i posts') % count
            href = "javascript:replace('posts', blip_url + '?q=posts&weeknum=%i')" % weeknum
            graph.add_bar (count, label=label, link=link, href=href)
        for i in range(curweek - weeknum):
            graph.add_bar (0)

        if isinstance (request.record, blip.db.Forum):
            sel = blip.db.Selection (blip.db.ForumPost,
                                     blip.db.ForumPost.forum == request.record)
            cnt = sel.count ()
            blip.db.ForumPost.select_author (sel)
        else:
            sel = blip.db.Selection (blip.db.ForumPost,
                                     blip.db.ForumPost.author == request.record)
            cnt = sel.count ()
            blip.db.ForumPost.select_forum (sel)
        sel.add_where (blip.db.ForumPost.weeknum <= blip.utils.weeknum())
        sel.order_by (blip.db.Desc (blip.db.ForumPost.datetime))
        posts = list(sel[:10])
        title = (blip.utils.gettext('Showing %i of %i commits:') % (len(posts), cnt))
        div = cls.get_posts_div (request, posts, title)
        tab.add_content (div)

        return response

    @staticmethod
    def get_posts_div (request, posts, title):
        div = blip.html.ActivityContainer (html_id='posts')
        div.set_title (title)
        for post in posts:
            if post.datetime is None:
                continue
            if isinstance (request.record, blip.db.Forum):
                act = blip.html.ActivityBox (subject=post['author'],
                                             datetime=post.datetime.strftime('%T'))
            else:
                act = blip.html.ActivityBox (subject=post['forum'],
                                             datetime=post.datetime.strftime('%T'))
            act.set_summary (post.title)
            div.add_activity (post.datetime.strftime('%Y-%m-%d'), act)
        return div


class ListPostsDiv (blip.web.ContentResponder):
    @classmethod
    def respond (cls, request):
        if request.query.get ('q', None) != 'posts':
            return None
        if request.record is None:
            return None
        if isinstance (request.record, blip.db.Forum) and request.record.type == u'List':
            sel = (blip.db.ForumPost.forum == request.record)
        elif isinstance (request.record, blip.db.Entity):
            sel = (blip.db.ForumPost.author == request.record)
        else:
            return None

        response = blip.web.WebResponse (request)

        weeknum = request.query.get('weeknum', None)
        weeknum = int(weeknum)
        thisweek = blip.utils.weeknum ()
        ago = thisweek - weeknum
        sel = blip.db.Selection (blip.db.ForumPost, sel)
        cnt = sel.count ()
        if isinstance (request.record, blip.db.Forum):
            blip.db.ForumPost.select_author (sel)
        else:
            blip.db.ForumPost.select_forum (sel)
        sel.add_where (blip.db.ForumPost.weeknum == weeknum)
        sel.order_by (blip.db.Desc (blip.db.ForumPost.datetime))
        posts = list(sel[:200])

        if ago == 0:
            if len(posts) == cnt:
                title = (blip.utils.gettext('Showing all %i posts from this week:')
                         % cnt)
            else:
                title = (blip.utils.gettext('Showing %i of %i posts from this week:')
                         % (len(posts), cnt))
        elif ago == 1:
            if len(posts) == cnt:
                title = (blip.utils.gettext('Showing all %i posts from last week:')
                         % cnt)
            else:
                title = (blip.utils.gettext('Showing %i of %i posts from last week:')
                         % (len(posts), cnt))
        else:
            if len(posts) == cnt:
                title = (blip.utils.gettext('Showing all %i posts from %i weeks ago:')
                         % (cnt, ago))
            else:
                title = (blip.utils.gettext('Showing %i of %i posts from %i weeks ago:')
                         % (len(posts), cnt, ago))

        div = ListPostsTab.get_posts_div (request, posts, title)
        response.payload = div
        return response


class PostMessageFormatter (blip.plugins.home.web.MessageFormatter):
    @classmethod
    def format_message (cls, message, record):
        if message.type == u'post':
            box = blip.html.ActivityBox (subject=record,
                                         datetime=message.datetime.strftime('%Y-%m-%d'))
            if isinstance (record, blip.db.Entity):
                span = blip.html.Span ('%i posts to ' % message.count)
                span.add_content (blip.html.Link (blip.db.Forum.get (message.pred)))
                box.add_info (span)
            else:
                box.add_info ('%i posts' % message.count)
            return box
        return None
