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

    return output_team (team, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.InfoBox (pulse.utils.gettext ('Teams'))
    teams = db.Entity.objects.filter (type='Team')
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
    teams = db.Entity.objects.filter (type='Team')
    teams = pulse.utils.attrsorted (list(teams), 'title')
    for team in teams:
        lbox = pulse.html.LinkBox (team)
        page.add_content (lbox)
    page.output (fd=kw.get('fd'))


def output_team (team, **kw):
    page = pulse.html.RecordPage (team, http=kw.get('http', True))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Modules and Documents
    mods = db.Branch.objects.filter (type='Module', module_entity_preds__pred=team)
    mods = pulse.utils.attrsorted (list(mods), 'title')
    if len(mods) > 0:
        modbox = pulse.html.InfoBox (pulse.utils.gettext ('Modules'))
        columns.add_to_column (1, modbox)
        brs = []
        for mod in mods:
            if mod.branchable_id in brs:
                continue
            brs.append (mod.branchable_id)
            modbox.add_link_box (mod)

    docs = db.Branch.objects.filter (type='Document', document_entity_preds__pred=team)
    docs = pulse.utils.attrsorted (list(docs), 'title')
    if len(docs) > 0:
        docbox = pulse.html.InfoBox (pulse.utils.gettext ('Documents'))
        columns.add_to_column (1, docbox)
        brs = []
        for doc in docs:
            if doc.branchable_id in brs:
                continue
            brs.append (doc.branchable_id)
            docbox.add_link_box (doc)

    page.output(fd=kw.get('fd'))
    return 0
