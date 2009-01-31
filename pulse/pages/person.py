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
    person = None
    kw = {'path' : path, 'query' : query}
    if len(path) == 1:
        return output_top (response, **kw)
    ident = '/' + '/'.join(path)
    person = db.Entity.objects.filter (ident=ident, type='Person')
    try:
        person = person[0]
    except IndexError:
        alias = db.Alias.objects.filter (ident=ident)
        try:
            person = alias[0].entity
        except:
            person = None
    if person == None:
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the person %s') % '/'.join(path[1:]),
            title=pulse.utils.gettext ('Person Not Found'))
        response.set_contents (page)
        return

    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, person, **kw)
    elif query.get('ajax', None) == 'commits':
        output_ajax_commits (response, person, **kw)
    elif query.get('ajax', None) == 'graphmap':
        output_ajax_graphmap (response, person, **kw)
    else:
        output_person (response, person, **kw)


synopsis_sort = -1
def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.SectionBox (pulse.utils.gettext ('People'))
    txt = (pulse.utils.gettext ('Pulse is watching %i people.') %
           db.Entity.objects.filter(type='Person').count() )
    box.add_content (pulse.html.Div (txt))

    columns = pulse.html.ColumnBox (2)
    box.add_content (columns)

    people = db.Entity.objects.filter (type='Person').order_by ('-mod_score')
    bl = pulse.html.BulletList ()
    bl.set_title (pulse.utils.gettext ('These people deserve a beer:'))
    columns.add_to_column (0, bl)
    for person in people[:6]:
        bl.add_link (person)

    people = db.Entity.objects.filter (type='Person').order_by ('-mod_score_diff')
    bl = pulse.html.BulletList ()
    bl.set_title (pulse.utils.gettext ('Up-and-coming rock stars:'))
    columns.add_to_column (1, bl)
    for person in people[:6]:
        bl.add_link (person)

    return box


def output_top (response, **kw):
    page = pulse.html.Page ()
    response.set_contents (page)
    page.set_title (pulse.utils.gettext ('People'))
    people = db.Entity.objects.filter (type='Person').order_by ('-mod_score')
    page.add_content(pulse.html.Div(pulse.utils.gettext('42 most active people:')))
    for person in people[:42]:
        lbox = pulse.html.LinkBox (person)
        lbox.add_fact (pulse.utils.gettext ('score'), str(person.mod_score))
        lbox.add_graph (pulse.config.graphs_root
                        + '/'.join(person.ident.split('/')[1:] + ['commits-tight.png']))
        page.add_content (lbox)


def output_person (response, person, **kw):
    page = pulse.html.Page (person)
    response.set_contents (page)

    # Teams
    rels = db.TeamMember.get_related (pred=person)
    rels = pulse.utils.attrsorted (list(rels), ('subj', 'title'))
    if len(rels) > 0:
        box = pulse.html.SidebarBox (pulse.utils.gettext ('Teams'))
        page.add_sidebar_content (box)
        for rel in rels:
            lbox = box.add_link_box (rel.subj)
            if rel.coordinator:
                lbox.add_badge ('coordinator')

    # Blog
    bident = '/blog' + person.ident
    blog = db.Forum.objects.filter (ident=bident)
    try:
        blog = blog[0]
        box = pulse.html.SidebarBox (pulse.utils.gettext ('Blog'))
        page.add_sidebar_content (box)
        dl = pulse.html.DefinitionList ()
        box.add_content (dl)
        for entry in blog.forum_posts.all()[:6]:
            link = pulse.html.Link (entry.web, entry.title)
            dl.add_term (link)
            if entry.datetime != None:
                dl.add_entry (entry.datetime.strftime('%Y-%m-%d %T'))
    except IndexError:
        pass

    # Tabs
    page.add_tab ('info', pulse.utils.gettext ('Info'))
    box = get_info_tab (person, **kw)
    page.add_to_tab ('info', box)

    page.add_tab ('activity', pulse.utils.gettext ('Activity'))
    page.add_tab ('hacking', pulse.utils.gettext ('Hacking'))


def output_ajax_tab (response, person, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'info':
        response.set_contents (get_info_tab (person, **kw))
    elif tab == 'activity':
        response.set_contents (get_activity_tab (person, **kw))
    elif tab == 'hacking':
        response.set_contents (get_hacking_tab (person, **kw))


def output_ajax_commits (response, person, **kw):
    query = kw.get('query', {})
    weeknum = int(query.get('weeknum', 0))
    thisweek = pulse.utils.weeknum (datetime.datetime.now())
    ago = thisweek - weeknum
    revs = db.Revision.select_revisions (person=person, weeknum=weeknum)
    cnt = revs.count()
    revs = revs[:20]
    if ago == 0:
        title = pulse.utils.gettext('Showing %i of %i commits from this week:') % (len(revs), cnt)
    elif ago == 1:
        title = pulse.utils.gettext('Showing %i of %i commits from last week:') % (len(revs), cnt)
    else:
        title = pulse.utils.gettext('Showing %i of %i commits from %i weeks ago:') % (len(revs), cnt, ago)
    response.set_contents (get_commits_div (person, revs, title))


def output_ajax_graphmap (response, person, **kw):
    query = kw.get ('query', {})
    id = query.get('id')
    num = query.get('num')
    filename = query.get('filename')
    
    of = db.OutputFile.objects.filter (type='graphs', ident=person.ident, filename=filename)
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, person.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'),
                                                 count=int(id), num=int(num), map_only=True)
        response.set_contents (graph)
    except IndexError:
        pass


def get_info_tab (person, **kw):
    facts = pulse.html.FactsTable ()

    if person.nick != None:
        facts.add_fact (pulse.utils.gettext ('Nick'), person.nick)
        facts.add_fact_divider ()
    if person.email != None:
        facts.add_fact (pulse.utils.gettext ('Email'),
                       pulse.html.Link ('mailto:' + person.email, person.email))
    if person.web != None:
        facts.add_fact (pulse.utils.gettext ('Website'), pulse.html.Link (person.web))
    facts.add_fact (pulse.utils.gettext ('Score'), str(person.mod_score))

    return facts


def get_activity_tab (person, **kw):
    box = pulse.html.Div ()
    of = db.OutputFile.objects.filter (type='graphs', ident=person.ident, filename='commits-0.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, person.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'))
        box.add_content (graph)
    except IndexError:
        pass

    revs = db.Revision.select_revisions (person=person)
    cnt = revs.count()
    revs = revs[:10]
    div = get_commits_div (person, revs,
                           pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    box.add_content (div)
    return box


def get_hacking_tab (person, **kw):
    columns = pulse.html.ColumnBox (2)

    # Modules
    rels = db.ModuleEntity.get_related (pred=person)
    rels = pulse.utils.attrsorted (list(rels), ('subj', 'title'),
                                   ('-', 'subj', 'is_default'),
                                   ('-', 'subj', 'scm_branch'))
    if len(rels) > 0:
        brs = []
        mods = pulse.utils.odict()
        bmaint = 0
        for rel in rels:
            mod = rel.subj
            if mod.branchable_id in brs:
                continue
            brs.append (mod.branchable_id)
            mods[mod] = rel
        box = pulse.html.InfoBox (pulse.utils.gettext ('Modules'))
        box.set_id ('modules')
        columns.add_to_column (0, box)
        for mod in mods:
            lbox = box.add_link_box (mod)
            if rel.maintainer:
                lbox.add_badge ('maintainer')
                bmaint += 1
        if 0 < bmaint < len(mods):
            box.add_badge_filter ('maintainer')

    # Documents
    rels = db.DocumentEntity.get_related (pred=person)
    rels = pulse.utils.attrsorted (list(rels), ('subj', 'title'),
                                   ('-', 'subj', 'is_default'),
                                   ('-', 'subj', 'scm_branch'))
    if len(rels) > 0:
        brs = []
        docs = pulse.utils.odict()
        bmaint = bauth = bedit = bpub = 0
        for rel in rels:
            doc = rel.subj
            if doc.branchable_id in brs:
                continue
            brs.append (doc.branchable_id)
            docs[doc] = rel
        box = pulse.html.InfoBox (pulse.utils.gettext ('Documents'))
        box.set_id ('documents')
        columns.add_to_column (1, box)
        for doc in docs:
            lbox = box.add_link_box (doc)
            rel = docs[doc]
            if rel.maintainer:
                lbox.add_badge ('maintainer')
                bmaint += 1
            if rel.author:
                lbox.add_badge ('author')
                bauth += 1
            if rel.editor:
                lbox.add_badge ('editor')
                bedit += 1
            if rel.publisher:
                lbox.add_badge ('publisher')
                bpub += 1
        if 0 < bmaint < len(docs):
            box.add_badge_filter ('maintainer')
        if 0 < bauth < len(docs):
            box.add_badge_filter ('author')
        if 0 < bedit < len(docs):
            box.add_badge_filter ('editor')
        if 0 < bpub < len(docs):
            box.add_badge_filter ('publisher')

    return columns


def get_commits_div (person, revs, title):
    div = pulse.html.Div (widget_id='commits')
    div.add_content (title)
    dl = pulse.html.DefinitionList ()
    div.add_content (dl)
    branches = {}
    curweek = None
    for rev in revs:
        if curweek != None and curweek != rev.weeknum:
            dl.add_divider ()
        curweek = rev.weeknum
        if not branches.has_key (rev.branch_id):
            branches[rev.branch_id] = rev.branch
        branch = branches[rev.branch_id]
        # FIXME: i18n word order
        span = pulse.html.Span (divider=pulse.html.SPACE)
        span.add_content (pulse.html.Link (branch.pulse_url, branch.branch_module))
        span.add_content ('on')
        span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
        dl.add_term (span)
        comment = rev.comment
        dl.add_entry (pulse.html.PopupLink.from_revision (rev, branch=branch))
    return div
