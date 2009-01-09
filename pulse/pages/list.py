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

def main (path, query, http=True, fd=None):
    team = None
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    if len(path) == 1:
        return output_top (**kw)
    ident = '/' + '/'.join(path)
    mlist = db.Forum.objects.filter (ident=ident, type='List')
    try:
        mlist = mlist[0]
    except IndexError:
        mlist = None
    if mlist == None:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Mailing List Not Found')
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the mailing list %s') % '/'.join(path[1:]),
            **kw)
        page.output(fd=fd)
        return 404

    if query.get('ajax', None) == 'tab':
        return output_ajax_tab (mlist, **kw)
    else:
        return output_list (mlist, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.InfoBox (pulse.utils.gettext ('Mailing Lists'))
    mlists = db.Forum.objects.filter (type='List').order_by ('-mod_score')
    box.add_content (str(mlists.count()))
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    for mlist in mlists[:12]:
        bl.add_item (pulse.html.Link (mlist.pulse_url, mlist.email))
    return box


def output_top (**kw):
    page = pulse.html.Page (http=kw.get('http', True))
    page.set_title (pulse.utils.gettext ('Mailing Lists'))
    mlists = db.Forum.objects.filter (type='List').order_by ('-mod_score')
    for mlist in mlists[:42]:
        lbox = pulse.html.LinkBox (mlist)
        page.add_content (lbox)
    page.output (fd=kw.get('fd'))


def output_list (mlist, **kw):
    page = pulse.html.RecordPage (mlist, http=kw.get('http', True))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Members
    box = get_members_box (mlist)
    page.add_sidebar_content (box)

    page.add_tab ('info', pulse.utils.gettext ('Info'))
    box = get_info_tab (mlist, **kw)
    page.add_to_tab ('info', box)

    page.add_tab ('activity', pulse.utils.gettext ('Activity'))

    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_tab (mlist, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    tab = query.get('tab', None)
    if tab == 'info':
        page.add_content (get_info_tab (mlist, **kw))
    elif tab == 'activity':
        page.add_content (get_activity_tab (mlist, **kw))
    page.output(fd=kw.get('fd'))
    return 0


def get_info_tab (mlist, **kw):
    facts = pulse.html.FactsTable()
    try:
        facts.add_fact (pulse.utils.gettext ('Description'),
                       module.localized_desc)
        facts.add_fact_sep ()
    except:
        pass

    facts.add_fact (pulse.utils.gettext ('List Info'),
                    pulse.html.Link (mlist.data.get('list_info')))
    facts.add_fact (pulse.utils.gettext ('Archives'),
                    pulse.html.Link (mlist.data.get('list_archive')))

    return facts


def get_activity_tab (mlist, **kw):
    box = pulse.html.Div ()
    dl = pulse.html.DefinitionList()
    box.add_content (dl)

    posts = db.ForumPost.objects.filter (forum=mlist).order_by ('-datetime')
    for post in posts[:20]:
        dl.add_term (post.title)
        dl.add_entry (pulse.html.Link (post.author))

    return box


def get_members_box (mlist):
    box = pulse.html.SidebarBox (pulse.utils.gettext ('Members'))
    return box
