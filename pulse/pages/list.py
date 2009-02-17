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

import datetime
import os

import pulse.config
import pulse.graphs
import pulse.html
import pulse.models as db
import pulse.scm
import pulse.utils

def main (response, path, query):
    team = None
    kw = {'path' : path, 'query' : query}
    if len(path) == 1:
        return output_top (response, **kw)
    ident = '/' + '/'.join(path)
    mlist = db.Forum.objects.filter (ident=ident, type='List')
    try:
        mlist = mlist[0]
    except IndexError:
        mlist = None
    if mlist == None:
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the mailing list %s') % '/'.join(path[1:]),
            title=pulse.utils.gettext ('Mailing List Not Found'))
        response.set_contents (page)
        return

    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, mlist, **kw)
    elif query.get('ajax', None) == 'graphmap':
        output_ajax_graphmap (response, mlist, **kw)
    elif query.get('ajax', None) == 'posts':
        output_ajax_posts (response, mlist, **kw)
    else:
        output_list (response, mlist, **kw)


# FIXME STORM
def FIXMEsynopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.SectionBox (pulse.utils.gettext ('Mailing Lists'))
    txt = (pulse.utils.gettext ('Pulse is watching %i mailing lists.  ') %
           db.Forum.objects.filter(type='List').count() )
    div = pulse.html.Div (txt)
    div.add_content ('Here are the 12 most active:')
    box.add_content (div);

    mlists = db.Forum.objects.filter (type='List').order_by ('-post_score')
    cols = pulse.html.ColumnBox (2)
    bl = (pulse.html.BulletList (), pulse.html.BulletList ())
    cols.add_to_column (0, bl[0])
    cols.add_to_column (1, bl[1])
    box.add_content (cols)
    i = 0
    for mlist in mlists[:12]:
        col = i >= 6 and 1 or 0
        bl[col].add_link (mlist.pulse_url, mlist.email)
        i += 1
    return box


def output_top (response, **kw):
    page = pulse.html.Page ()
    response.set_contents (page)
    page.set_title (pulse.utils.gettext ('Mailing Lists'))
    mlists = db.Forum.objects.filter (type='List').order_by ('-post_score')
    for mlist in mlists[:42]:
        lbox = pulse.html.LinkBox (mlist)
        page.add_content (lbox)


def output_list (response, mlist, **kw):
    page = pulse.html.Page (mlist)
    response.set_contents (page)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Members
    box = get_members_box (mlist)
    page.add_sidebar_content (box)

    page.add_tab ('info', pulse.utils.gettext ('Info'))
    box = get_info_tab (mlist, **kw)
    page.add_to_tab ('info', box)

    page.add_tab ('activity', pulse.utils.gettext ('Activity'))


def output_ajax_tab (response, mlist, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'info':
        response.set_contents (get_info_tab (mlist, **kw))
    elif tab == 'activity':
        response.set_contents (get_activity_tab (mlist, **kw))


def output_ajax_graphmap (response, mlist, **kw):
    query = kw.get ('query', {})
    id = query.get('id')
    num = query.get('num')
    filename = query.get('filename')
    
    of = db.OutputFile.objects.filter (type='graphs', ident=mlist.ident, filename=filename)
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, mlist.pulse_url, 'posts',
                                                 pulse.utils.gettext ('%i posts'),
                                                 count=int(id), num=int(num), map_only=True)
        response.set_contents (graph)
    except IndexError:
        pass


def output_ajax_posts (response, mlist, **kw):
    query = kw.get ('query', {})
    weeknum = query.get('weeknum', None)
    if weeknum != None:
        weeknum = int(weeknum)
    else:
        weeknum = pulse.utils.weeknum ()
    thisweek = pulse.utils.weeknum ()
    ago = thisweek - weeknum
    posts = db.ForumPost.objects.filter (forum=mlist,
                                         weeknum=weeknum,
                                         datetime__isnull=False)
    posts = list(posts)
    if ago == 0:
        title = (pulse.utils.gettext('Showing %i posts from this week:')
                 % len(posts))
    elif ago == 1:
        title = (pulse.utils.gettext('Showing %i posts from last week:')
                 % len(posts))
    else:
        title = (pulse.utils.gettext('Showing %i posts from %i weeks ago:')
                 % (len(posts), ago))

    response.set_contents (get_posts_div (mlist, posts, title))


def get_info_tab (mlist, **kw):
    facts = pulse.html.FactsTable()
    try:
        facts.add_fact (pulse.utils.gettext ('Description'),
                       module.localized_desc)
        facts.add_fact_divider ()
    except:
        pass

    facts.add_fact (pulse.utils.gettext ('List Info'),
                    pulse.html.Link (mlist.data.get('list_info')))
    facts.add_fact (pulse.utils.gettext ('Archives'),
                    pulse.html.Link (mlist.data.get('list_archive')))

    facts.add_fact_divider ()
    facts.add_fact (pulse.utils.gettext ('Score'),
                    str(mlist.post_score))

    return facts


def get_activity_tab (mlist, **kw):
    box = pulse.html.Div ()
    of = db.OutputFile.objects.filter (type='graphs', ident=mlist.ident, filename='posts-0.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, mlist.pulse_url, 'posts',
                                                 pulse.utils.gettext ('%i posts'))
        box.add_content (graph)
    except IndexError:
        pass

    weeknum = pulse.utils.weeknum()
    posts = db.ForumPost.objects.filter (forum=mlist,
                                         weeknum=weeknum,
                                         datetime__isnull=False)
    posts = list(posts)
    title = pulse.utils.gettext ('Showing %i posts from this week') % len(posts)
    box.add_content (get_posts_div (mlist, posts, title))

    return box


def get_posts_div (mlist, posts, title):
    div = pulse.html.Div (widget_id='posts')
    div.add_content (title)
    table = pulse.html.Table ()
    div.add_content (table)

    byid = pulse.utils.odict ()
    for post in posts:
        byid.setdefault (post.id, {'post': None, 'children': []})
        byid[post.id]['post'] = post
        if post.parent_id != None:
            byid.setdefault (post.parent_id, {'post': None, 'children': []})
            byid[post.parent_id]['children'].append (post.id)
    def add_row (key, post, depth):
        author = db.Entity.get_cached (post.author_id)
        depth = min (depth, 8)
        # FIXME: would be better to do this with colspan so that line wraps
        # don't look funky.  But we'll have to change html.Table for that.
        prefix = '\xc2\xa0' * (2 * depth)
        title = pulse.html.EllipsizedLabel (post.title, 40 - depth, truncate=True)
        if post.web != None:
            title = pulse.html.Link (post.web, title)
        title = pulse.html.Span (prefix, title)
        table.add_row (title,
                       post.datetime.strftime('%Y-%m-%d'),
                       pulse.html.Link (author))
        for child in byid[key]['children']:
            childpost = byid[child]['post']
            if childpost == None:
                continue
            add_row (child, childpost, depth + 1)
    for key in byid.keys():
        post = byid[key]['post']
        if post == None:
            continue
        if post.parent_id != None:
            if byid.get (post.parent_id, {'post': None})['post'] != None:
                continue
        add_row (key, post, 0)

    return div


def get_members_box (mlist):
    box = pulse.html.SidebarBox (pulse.utils.gettext ('Members'))
    return box
