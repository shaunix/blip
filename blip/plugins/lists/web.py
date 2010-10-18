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
import blinq.reqs.web

import blip.db
import blip.html
import blip.utils
import blip.web

import blip.plugins.home.web
import blip.plugins.index.web

class AllListsResponder (blip.web.PageResponder):
    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) != 1 or request.path[0] != 'list':
            return None

        response = blip.web.WebResponse (request)

        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext ('Mailing Lists'))
        cont = blip.html.ContainerBox ()
        cont.set_show_icons (False)
        cont.add_sort_link ('title', blip.utils.gettext ('title'), 1)
        cont.add_sort_link ('score', blip.utils.gettext ('score'))
        page.add_content (cont)

        lists = blip.db.Forum.select (type=u'List')
        lists = blinq.utils.attrsorted (list(lists), 'title')
        for ml in lists:
            lbox = cont.add_link_box (ml)
            if ml.score is not None:
                lbox.add_fact (blip.utils.gettext ('score'),
                               blip.html.Span (str(ml.score),
                                               html_class='score'))
            lbox.add_graph (blip.html.SparkGraph (ml.blip_url, 'posts'))

        response.payload = page
        return response

class ListsIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response):
        """Construct an info box for the index page"""
        mls = blip.db.Forum.select (type=u'List')

        cnt = mls.count()
        if cnt == 0:
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

        bl.add_link (blinq.config.web_root_url + 'list',
                     blip.utils.gettext ('All %i lists...' % cnt))


class ListSparkResponder (blip.web.DataResponder):
    @classmethod
    def respond (cls, request):
        if request.query.get ('d', None) != 'spark':
            return None
        if request.record is None:
            return None
        if not (isinstance (request.record, blip.db.Forum) and request.record.type == u'List'):
            return None

        response = blip.web.WebResponse (request)
        json = blinq.reqs.web.JsonPayload ()
        response.payload = json

        thisweek = blip.utils.weeknum()
        store = blip.db.get_store (blip.db.ForumPost)
        sel = store.find ((blip.db.ForumPost.weeknum, blip.db.Count('*')),
                          blip.db.ForumPost.forum == request.record,
                          blip.db.ForumPost.weeknum > (thisweek - 208))
        sel = sel.group_by (blip.db.ForumPost.weeknum)
        stats = [0 for i in range(208)]
        for week, cnt in list(sel):
            stats[week - (thisweek - 207)] = cnt
        json.set_data (stats)

        return response


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
        page.add_trail_link (blinq.config.web_root_url + 'list',
                             blip.utils.gettext ('Lists'))
        response.payload = page
        return response

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) != 3 or request.path[0] != 'list':
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
        facts.add_fact (blip.utils.gettext ('Mailing List'), request.record.title)

        facts.start_fact_group ()
        if request.record.data.get('listinfo') is not None:
            facts.add_fact (blip.utils.gettext ('List Info'),
                            blip.html.Link (request.record.data['listinfo']))
        if request.record.data.get('archive') is not None:
            facts.add_fact (blip.utils.gettext ('Archives'),
                            blip.html.Link (request.record.data['archive']))

        if request.record.updated is not None:
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Last Updated'),
                            request.record.updated.strftime('%Y-%m-%d %T'))

        facts.start_fact_group ()
        span = blip.html.Span (divider=blip.html.BULLET)
        store = blip.db.get_store (blip.db.Entity)
        using = store.using (blip.db.Entity,
                             blip.db.Join (blip.db.ForumPost,
                                           blip.db.ForumPost.author_ident == blip.db.Entity.ident))
        cnt = blip.db.Count (blip.db.ForumPost.ident)
        sel = using.find (blip.db.Entity, blip.db.ForumPost.forum_ident == request.record.ident)
        sel = sel.group_by (blip.db.Entity.ident)
        sel = sel.order_by (blip.db.Desc (cnt))
        for ent in sel[:10]:
            span.add_content (blip.html.Link (ent))
        facts.add_fact (blip.utils.gettext ('Top Posters'), span)

        return tab

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) != 3 or request.path[0] != 'list':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
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
        title = (blip.utils.gettext('Showing %i of %i posts:') % (len(posts), cnt))
        div = ListPostsDiv.get_posts_div (request, posts, title)
        tab.add_content (div)

        return response


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
        sel.add_where (blip.db.ForumPost.weeknum == weeknum)
        cnt = sel.count ()
        if isinstance (request.record, blip.db.Forum):
            blip.db.ForumPost.select_author (sel)
        else:
            blip.db.ForumPost.select_forum (sel)
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

        div = ListPostsDiv.get_posts_div (request, posts, title)
        response.payload = div
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


class ListThreadsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if request.record is None:
            return
        if not (isinstance (request.record, blip.db.Forum) and request.record.type == u'List'):
            return
        cnt = blip.db.ForumPost.select (forum=request.record).count ()
        if cnt > 0:
            page.add_tab ('threads',
                          blip.utils.gettext ('Threads'),
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if not blip.html.TabProvider.match_tab (request, 'threads'):
            return None
        if not (isinstance (request.record, blip.db.Forum) and request.record.type == u'List'):
            return None
        response = blip.web.WebResponse (request)
        tab = blip.html.PaddingBox ()
        response.payload = tab
        graph = blip.html.BarGraph ()
        tab.add_content (graph)

        store = blip.db.get_store (blip.db.ForumPost)
        sel = store.find ((blip.db.ForumPost.weeknum, blip.db.Count('*')),
                          blip.db.And (blip.db.ForumPost.forum == request.record,
                                       blip.db.ForumPost.parent == None))
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
            link = blip.utils.gettext ('%i threads') % count
            href = "javascript:replace('threads', blip_url + '?q=threads&weeknum=%i')" % weeknum
            graph.add_bar (count, label=label, link=link, href=href)
        for i in range(curweek - weeknum):
            graph.add_bar (0)

        sel = blip.db.Selection (blip.db.ForumPost,
                                 blip.db.And (blip.db.ForumPost.forum == request.record,
                                              blip.db.ForumPost.parent == None))
        cnt = sel.count ()
        blip.db.ForumPost.select_author (sel)
        sel.add_where (blip.db.ForumPost.weeknum <= blip.utils.weeknum())
        sel.order_by (blip.db.Desc (blip.db.ForumPost.datetime))
        threads = list(sel[:10])
        title = (blip.utils.gettext('Showing %i of %i threads:') % (len(threads), cnt))
        div = ListThreadsDiv.get_threads_div (request, threads, title)
        tab.add_content (div)

        return response


class ListThreadsDiv (blip.web.ContentResponder):
    @classmethod
    def respond (cls, request):
        if request.query.get ('q', None) != 'threads':
            return None
        if request.record is None:
            return None
        if not (isinstance (request.record, blip.db.Forum) and request.record.type == u'List'):
            return None

        response = blip.web.WebResponse (request)

        weeknum = request.query.get('weeknum', None)
        weeknum = int(weeknum)
        thisweek = blip.utils.weeknum ()
        ago = thisweek - weeknum
        sel = blip.db.Selection (blip.db.ForumPost,
                                 blip.db.ForumPost.forum == request.record,
                                 blip.db.ForumPost.parent == None)
        sel.add_where (blip.db.ForumPost.weeknum == weeknum)
        cnt = sel.count ()
        blip.db.ForumPost.select_author (sel)
        sel.order_by (blip.db.Desc (blip.db.ForumPost.datetime))
        threads = list(sel[:200])

        if ago == 0:
            if len(threads) == cnt:
                title = (blip.utils.gettext('Showing all %i threads from this week:')
                         % cnt)
            else:
                title = (blip.utils.gettext('Showing %i of %i threads from this week:')
                         % (len(threads), cnt))
        elif ago == 1:
            if len(threads) == cnt:
                title = (blip.utils.gettext('Showing all %i threads from last week:')
                         % cnt)
            else:
                title = (blip.utils.gettext('Showing %i of %i threads from last week:')
                         % (len(threads), cnt))
        else:
            if len(threads) == cnt:
                title = (blip.utils.gettext('Showing all %i threads from %i weeks ago:')
                         % (cnt, ago))
            else:
                title = (blip.utils.gettext('Showing %i of %i threads from %i weeks ago:')
                         % (len(threads), cnt, ago))

        div = ListThreadsDiv.get_threads_div (request, threads, title)
        response.payload = div
        return response

    @staticmethod
    def get_threads_div (request, threads, title):
        div = blip.html.ActivityContainer (html_id='threads')
        div.set_title (title)
        for thread in threads:
            if thread.datetime is None:
                continue
            act = blip.html.ActivityBox (subject=thread.title,
                                         datetime=thread.datetime.strftime('%T'))
            store = blip.db.get_store (blip.db.ForumPost)
            idents = [thread.ident]
            children = 1
            while True:
                sel = store.find (blip.db.ForumPost.ident,
                                  blip.db.ForumPost.parent_ident.is_in (idents))
                idents = list(sel)
                children += len(idents)
                if len(idents) == 0:
                    break
            act.add_info (blip.utils.gettext ('%i posts') % children)
            span = blip.html.Span (blip.utils.gettext ('started by '),
                                   divider=blip.html.SPACE)
            span.add_content (blip.html.Link (thread['author']))
            act.add_info (span)
            div.add_activity (thread.datetime.strftime('%Y-%m-%d'), act)
        return div


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

