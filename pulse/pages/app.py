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

import math
import os

import pulse.config
import pulse.html
import pulse.models as db
import pulse.scm
import pulse.utils

people_cache = {}

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 4:
        branchables = db.Branchable.objects.filter (ident=('/' + '/'.join(path)))
        try:
            branchable = branchables[0]
        except IndexError:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Application Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('app', pulse.utils.gettext ('All Applications'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the application %s') % path[3],
                **kw)
            page.output(fd=fd)
            return 404

        app = branchable.default
        if app == None:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Default Branch Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('app', pulse.utils.gettext ('All Applications'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch for the application %s') % path[3],
                **kw)
            page.output(fd=fd)
            return 404

    elif len(path) == 5:
        apps = db.Branch.objects.filter (ident=('/' + '/'.join(path)))
        try:
            app = apps[0]
        except IndexError:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Application Not Found')
            page = pulse.html.PageNotFound (
                (pulse.utils.gettext ('Pulse could not find the branch %s of the application %s')
                 % (path[4], path[3])),
                **kw)
            page.output(fd=fd)
            return 404
    else:
        # FIXME: redirect to /set or something
        pass

    return output_app (app, path, query, http, fd)


def output_app (app, path=[], query=[], http=True, fd=None):
    page = pulse.html.RecordPage (app, http=http)
    checkout = pulse.scm.Checkout.from_record (app, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(app.branchable.branches.all()), 'scm_branch')
    if len(branches) > 1:
        for b in branches:
            if b.ident != app.ident:
                page.add_sublink (b.pulse_url, b.ident.split('/')[-1])
            else:
                page.add_sublink (None, b.ident.split('/')[-1])

    if app.data.has_key ('screenshot'):
        page.add_screenshot (app.data['screenshot'])

    sep = False
    try:
        desc = app.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    rels = db.SetModule.get_related (pred=app.parent)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(set.pulse_url + '/prog', set.title) for set in sets])
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    page.add_fact (pulse.utils.gettext ('Module'), pulse.html.Link (app.parent))

    if sep: page.add_fact_sep ()
    
    page.add_fact (pulse.utils.gettext ('Location'), checkout.get_location (app.scm_dir, app.scm_file))

    if app.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (app.mod_datetime.strftime('%Y-%m-%d %T'))
        if app.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (app.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    columns.add_to_column (0, box)
    rels = db.ModuleEntity.get_related (subj=app.parent)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
            people_cache[rel.pred.id] = rel.pred
        for person in pulse.utils.attrsorted (people.keys(), 'title'):
            lbox = box.add_link_box (person)
            rel = people[person]
            if rel.maintainer:
                lbox.add_badge ('maintainer')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))

    # Documentation
    rels = db.Documentation.get_related (subj=app)
    box = pulse.html.InfoBox ('documentation', pulse.utils.gettext ('Documentation'))
    columns.add_to_column (1, box)
    if len(rels) > 0:
        docs = pulse.utils.attrsorted ([rel.pred for rel in rels], 'title')
        for doc in docs:
            lbox = box.add_link_box (doc)
            res = doc.select_children ('Translation')
            lbox.add_fact (None, pulse.utils.gettext ('%i translations') % res.count())
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documentation') ))

    page.output(fd=fd)

    return 0
