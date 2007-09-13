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

import pulse.config as config
import pulse.db as db
import pulse.html as html
import pulse.utils as utils

def main (path = [], query = {}, http = True):
    kw = {'http': http}
    if len(path) == 1:
        teams = db.TranslationTeam.select ()
        print_teams (teams, path, query, http=http)
        kw['title'] = 'Translation Teams'
    elif len(path) > 1:
        teams = db.TranslationTeam.selectBy (ident = 'l10n/' + path[1])
        if teams.count() == 0:
            kw['title'] = 'Translation Team Not Found'
            kw['pages'] = [('l10n', 'All Translation Teams')]
            page = html.PageNotFound (
                'Could not find the translation team "%s"' % path[1],
                **kw)
            page.output()
            return 404
        else:
            print_team (teams[0], path, query, http=http)
    return 0

def print_teams (teams, path=[], query={}, title='Translation Teams', http=True):
    kw = {'http': http, 'title': title}

    page = html.Page (**kw)

    teamd = {}
    for team in teams:
        teamd[team.name] = team
    for key in utils.isorted (teamd.keys()):
        team = teamd[key]
        syn = html.SynopsisDiv (team)
        page.add (syn)

        members = team.members
        affils = {}
        for member in members:
            affild = {'href': config.webroot (member.resource.ident)}
            affild['name'] = member.resource.name
            if member.comment == 'coordinator':
                affild['comment'] = '(Coordinator)'
            else:
                affild['comment'] = None
            affils[member.resource.name] = affild
        for key in utils.isorted (affils.keys()):
            syn.add_affiliation ('Members', **affils[key])

    page.output()

def print_team (team, path=[], query={}, http=True):
    kw = {'http': http, 'title': team.name}

    page = html.Page (**kw)
    # FIXME
    page.add (html.SynopsisDiv (team))

    page.output()

