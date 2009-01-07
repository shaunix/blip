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
    team = db.Entity.objects.filter (ident=ident, type='Team')
    try:
        team = team[0]
    except IndexError:
        alias = db.Alias.objects.filter (ident=ident)
        try:
            team = alias[0].entity
        except:
            team = None
    if team == None:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Team Not Found')
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the team %s') % '/'.join(path[1:]),
            **kw)
        page.output(fd=fd)
        return 404

    if query.get('ajax', None) == 'tab':
        return output_ajax_tab (team, **kw)
    else:
        return output_team (team, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.InfoBox (pulse.utils.gettext ('Teams'))
    teams = db.Entity.objects.filter (type='Team', parent__isnull=True)
    teams = pulse.utils.attrsorted (list(teams), 'title')
    box.add_content (pulse.html.Div (pulse.utils.gettext ('Root for the home team:')))
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    for team in teams:
        bl.add_item (pulse.html.Link (team))
    return box


def output_top (**kw):
    page = pulse.html.Page (http=kw.get('http', True))
    page.set_title (pulse.utils.gettext ('Teams'))
    teams = db.Entity.objects.filter (type='Team', parent__isnull=True)
    teams = pulse.utils.attrsorted (list(teams), 'title')
    for team in teams:
        lbox = pulse.html.LinkBox (team)
        page.add_content (lbox)
    page.output (fd=kw.get('fd'))


def output_team (team, **kw):
    page = pulse.html.RecordPage (team, http=kw.get('http', True))

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

    cnt = team.children.count()
    if cnt > 0:
        page.add_tab ('subteams', pulse.utils.gettext ('Subteams (%i)') % cnt)

    cnt = db.Branch.objects.filter (type='Module', document_entity_preds__pred=team).count()
    if cnt > 0:
        page.add_tab ('doc', pulse.utils.gettext ('Modules (%i)') % cnt)

    cnt = db.Branch.objects.filter (type='Document', document_entity_preds__pred=team).count()
    if cnt > 0:
        page.add_tab ('doc', pulse.utils.gettext ('Documents (%i)') % cnt)

    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_tab (team, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    tab = query.get('tab', None)
    if tab == 'info':
        page.add_content (get_info_tab (team, **kw))
    elif tab == 'subteams':
        page.add_content (get_subteams_tab (team, **kw))
    elif tab == 'mod':
        page.add_content (get_mod_tab (team, **kw))
    elif tab == 'doc':
        page.add_content (get_doc_tab (team, **kw))
    page.output(fd=kw.get('fd'))
    return 0


def get_info_tab (team, **kw):
    facts = pulse.html.FactsTable()
    sep = False
    try:
        facts.add_fact (pulse.utils.gettext ('Description'),
                       module.localized_desc)
        sep = True
    except:
        pass

    if team.web != None:
        facts.add_fact (pulse.utils.gettext ('Website'), pulse.html.Link (team.web))

    return facts


def get_subteams_tab (team, **kw):
    bl = pulse.html.BulletList ()
    for subteam in pulse.utils.attrsorted (list(team.children.all()), 'title'):
        bl.add_item (pulse.html.Link (subteam))
    return bl


def get_mod_tab (team, **kw):
    box = pulse.html.ContainerBox ()
    rels = db.ModuleEntity.get_related (pred=team)
    brs = []
    mods = pulse.utils.odict()
    for rel in pulse.utils.attrsorted (list(rels), ('subj', 'title'),
                                       ('-', 'subj', 'is_default'),
                                       ('-', 'subj', 'scm_branch')):
        mod = rel.subj
        if mod.branchable_id in brs:
            continue
        brs.append (mod.branchable_id)
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
    rels = db.DocumentEntity.get_related (pred=team)
    brs = []
    docs = pulse.utils.odict()
    bmaint = bauth = bedit = bpub = 0
    for rel in pulse.utils.attrsorted (list(rels),
                                       ('subj', 'title'),
                                       ('-', 'subj', 'is_default'),
                                       ('-', 'subj', 'scm_branch')):
        doc = rel.subj
        if doc.branchable_id in brs:
            continue
        brs.append (doc.branchable_id)
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
    rels = db.TeamMember.get_related (subj=team)
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
