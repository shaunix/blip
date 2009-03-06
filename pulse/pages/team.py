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
import pulse.db
import pulse.graphs
import pulse.html
import pulse.scm
import pulse.utils

def main (response, path, query):
    team = None
    kw = {'path' : path, 'query' : query}
    if len(path) == 1:
        return output_top (response, **kw)
    ident = '/' + '/'.join(path)
    team = pulse.db.Entity.get (ident)
    if team == None:
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the team %s') % '/'.join(path[1:]),
            title=pulse.utils.gettext ('Team Not Found'))
        response.set_contents (page)
        return

    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, team, **kw)
    else:
        output_team (response, team, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.SidebarBox (title=pulse.utils.gettext ('Teams'))
    teams = pulse.db.Entity.select (type=u'Team', parent_ident=None)
    teams = pulse.utils.attrsorted (list(teams), 'title')
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    for team in teams:
        bl.add_link (team)
    return box


def output_top (response, **kw):
    page = pulse.html.Page ()
    response.set_contents (page)
    page.set_title (pulse.utils.gettext ('Teams'))
    teams = pulse.db.Entity.select (type=u'Team', parent=None)
    teams = pulse.utils.attrsorted (list(teams), 'title')
    for team in teams:
        lbox = pulse.html.LinkBox (team)
        page.add_content (lbox)


def output_team (response, team, **kw):
    page = pulse.html.Page (team)
    response.set_contents (page)

    page.set_sublinks_divider (pulse.html.TRIANGLE)
    page.add_sublink (pulse.config.web_root + 'team', pulse.utils.gettext ('Teams'))
    for parent in get_parents (team):
        page.add_sublink (parent.pulse_url, parent.title)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Members
    box = get_members_box (team)
    page.add_sidebar_content (box)

    page.add_tab ('info', pulse.utils.gettext ('Info'))
    box = get_info_tab (team, **kw)
    page.add_to_tab ('info', box)

    cnt = team.select_children().count()
    if cnt > 0:
        page.add_tab ('subteams', pulse.utils.gettext ('Subteams (%i)') % cnt)

    cnt = pulse.db.Branch.select (pulse.db.Branch.type == u'Module',
                                  pulse.db.Branch.ident == pulse.db.ModuleEntity.subj_ident,
                                  pulse.db.ModuleEntity.pred_ident == team.ident)
    cnt = cnt.count ()
    if cnt > 0:
        page.add_tab ('modules', pulse.utils.gettext ('Modules (%i)') % cnt)

    cnt = pulse.db.Branch.select (pulse.db.Branch.type == u'Document',
                                  pulse.db.Branch.ident == pulse.db.DocumentEntity.subj_ident,
                                  pulse.db.DocumentEntity.pred_ident == team.ident)
    cnt = cnt.count ()
    if cnt > 0:
        page.add_tab ('documents', pulse.utils.gettext ('Documents (%i)') % cnt)


def output_ajax_tab (response, team, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'info':
        response.set_contents (get_info_tab (team, **kw))
    elif tab == 'subteams':
        response.set_contents (get_subteams_tab (team, **kw))
    elif tab == 'modules':
        response.set_contents (get_mod_tab (team, **kw))
    elif tab == 'documents':
        response.set_contents (get_doc_tab (team, **kw))


def get_info_tab (team, **kw):
    facts = pulse.html.FactsTable()
    sep = False
    try:
        facts.add_fact (pulse.utils.gettext ('Description'),
                       team.localized_desc)
        sep = True
    except:
        pass

    if team.web != None:
        facts.add_fact (pulse.utils.gettext ('Website'), pulse.html.Link (team.web))

    return facts


def get_subteams_tab (team, **kw):
    bl = pulse.html.BulletList ()
    for subteam in pulse.utils.attrsorted (list(team.select_children()), 'title'):
        bl.add_link (subteam)
    return bl


def get_mod_tab (team, **kw):
    box = pulse.html.ContainerBox ()
    rels = pulse.db.ModuleEntity.get_related (pred=team)
    brs = []
    mods = pulse.utils.odict()
    for rel in pulse.utils.attrsorted (list(rels),
                                       ('subj', 'title'),
                                       ('-', 'subj', 'is_default'),
                                       ('-', 'subj', 'scm_branch')):
        mod = rel.subj
        if mod.branchable in brs:
            continue
        brs.append (mod.branchable)
        mods[mod] = rel
    for mod in mods.keys():
        lbox = box.add_link_box (mod)
        rel = mods[mod]
        if rel.maintainer:
            lbox.add_badge ('maintainer')
    return box


def get_doc_tab (team, **kw):
    box = pulse.html.ContainerBox ()
    box.set_id ('docs')
    rels = pulse.db.DocumentEntity.get_related (pred=team)
    brs = []
    docs = pulse.utils.odict()
    bmaint = bauth = bedit = bpub = 0
    for rel in pulse.utils.attrsorted (list(rels),
                                       ('subj', 'title'),
                                       ('-', 'subj', 'is_default'),
                                       ('-', 'subj', 'scm_branch')):
        doc = rel.subj
        if doc.branchable in brs:
            continue
        brs.append (doc.branchable)
        docs[doc] = rel
    for doc in docs.keys():
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
    return box


def get_members_box (team):
    box = pulse.html.SidebarBox (pulse.utils.gettext ('Members'))
    rels = pulse.db.TeamMember.get_related (subj=team)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
        for person in pulse.utils.attrsorted (people.keys(), 'title'):
            lbox = box.add_link_box (person)
            rel = people[person]
            if rel.coordinator:
                lbox.add_badge ('coordinator')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No members') ))
    return box


def get_parents (team):
    """Get a list of the parents of a team"""
    parent = team.parent
    if parent == None:
        return []
    else:
        parents = get_parents (parent)
        return parents + [parent]
