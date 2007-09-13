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
    kw = {'http': http}
    if len(path) == 1:
        lists = db.MailList.select ()
        print_lists (lists, path, query, http=http)
    elif len(path) > 1:
        lists = db.MailList.selectBy (ident = 'lists/' + path[1])
        if lists.count() == 0:
            kw['title'] = 'Mailing List Not Found'
            kw['pages'] = [('lists', 'All Mailing Lists')]
            page = html.PageNotFound (
                'Could not find the mailing list "%s"' % path[1],
                **kw)
            page.output()
            return 404
        else:
            print_list (lists[0], path, query, http=http)
    return 0


def print_lists (lists, path=[], query={}, title='Mailing Lists', http=True):
    kw = {'http': http, 'title': title}

    page = html.Page (**kw)

    listd = {}
    for list in lists:
        listd[list.name] = list
    for key in utils.isorted (listd.keys()):
        list = listd[key]
        syn = html.SynopsisDiv (list)
        page.add (syn)

        for type in ((db.Module, 'Modules'),
                     (db.Document, 'Documents'),
                     (db.TranslationTeam, 'Translation Teams')):
            rels = list.get_related ('mail_list', type[0], invert=True)
            affils = {}
            for r in rels:
                affild = {'href': config.webroot (r.resource.ident)}
                affild['name'] = r.resource.name
                affild['comment'] = None
                affils[r.resource.name] = affild
            for key in utils.isorted (affils.keys()):
                syn.add_affiliation (type[1], **affils[key])

        syn.add_graph ('Commit Activity', None,
                       '%sgraphs/%s/all.png' % (config.webroot, list.ident),
                       'Mailing List Activity for %s' % list.name)
    # end for key

    page.output()

def print_list (list, path=[], query={}, http=True):
    kw = {'http': http, 'title': list.name}

    page = html.Page (**kw)
    # FIXME
    page.add (html.SynopsisDiv (list))

    page.output()

