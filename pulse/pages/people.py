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

def main (path=[], query={}, http=True):
    if len(path) == 1:
        people = db.Person.select ()
        print_people (people, path, query, http=http)
    else:
        people = db.Person.selectBy (ident = 'people/' + path[1])
        if people.count() == 0:
            kw = {'http': http}
            kw['title'] = 'Person Not Found'
            kw['pages'] = [('people', 'All People')]
            page = html.PageNotFound (
                'Could not find the person with username "%s"' % path[1],
                **kw)
            page.output()
            return 404
        else:
            print_person (people[0], path, query, http=http)
    return 0


def print_people (people, path=[], query={}, title='People', http=True):
    kw = {'http': http, 'title': title}

    page = html.Page (**kw)

    persond = {}
    for person in people:
        persond[person.name] = person
    for key in utils.isorted (persond.keys()):
        person = persond[key]
        syn = html.SynopsisDiv (person)
        page.add (syn)

        # Add module developer affiliations
        rels = person.developer_for
        affils = {}
        for rel in rels:
            affild = {'href': config.webroot (rel.resource.ident)}
            affild['name'] = rel.resource.name
            if rel.comment == 'maintainer':
                affild['comment'] = '(Maintainer)'
            else:
                affild['comment'] = None
            affils[rel.resource.name] = affild
        for key in utils.isorted (affils.keys()):
            syn.add_affiliation ('Developer', **affils[key])

        # Add translation team memberships
        rels = person.translator_for
        affils = {}
        for rel in rels:
            affild = {'href': config.webroot (rel.resource.ident)}
            affild['name'] = rel.resource.name
            if rel.comment == 'coordinator':
                affild['comment'] = '(Coordinator)'
            else:
                affild['comment'] = None
            affils[rel.resource.name] = affild
        for key in utils.isorted (affils.keys()):
            syn.add_affiliation ('Translator', **affils[key])

        syn.add_graph ('Commit Activity', None,
                       '%sgraphs/%s/rcs.png' % (config.webroot, person.ident),
                       'Commit Activity for %s' % person.name)
        syn.add_graph ('Mailing List Activity', None,
                       '%sgraphs/%s/ml.png' % (config.webroot, person.ident),
                       'Mailing List Activity for %s' % person.name)
    # end for key

    page.output()

def print_person (person, path=[], query={}, http=True):
    kw = {'http': http, 'title': person.name}

    page = html.Page (**kw)
    # FIXME
    page.add (html.SynopsisDiv (person))

    page.output()

