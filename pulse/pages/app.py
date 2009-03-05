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

"""Output information about applications"""

import pulse.config
import pulse.db
import pulse.html
import pulse.scm
import pulse.utils

import pulse.pages.mod

def main (response, path, query):
    """Output information about applications"""
    ident = u'/' + u'/'.join(path)
    if len(path) == 4:
        branches = list(pulse.db.Branch.select (branchable=ident))
        if len(branches) == 0:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the application %s')
                % path[3],
                title=pulse.utils.gettext ('Application Not Found'))
            response.set_contents (page)
            return

        app = [branch for branch in branches if branch.is_default]
        if len(app) == 0:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch'
                                     ' for the application %s')
                % path[3],
                title=pulse.utils.gettext ('Default Branch Not Found'))
            response.set_contents (page)
            return
        app = app[0]

    elif len(path) == 5:
        app = pulse.db.Branch.get (ident)
        if app == None:
            page = pulse.html.PageNotFound (
                (pulse.utils.gettext ('Pulse could not find the branch %s'
                                      ' of the application %s')
                 % (path[4], path[3])),
                title=pulse.utils.gettext ('Application Not Found'))
            response.set_contents (page)
            return
    else:
        # FIXME: redirect to /set or something
        pass

    return output_app (response, app, path=path, query=query)


def output_app (response, app, **kw):
    """Output information about an application"""
    page = pulse.html.Page (app)
    response.set_contents (page)
    checkout = pulse.scm.Checkout.from_record (app, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(pulse.db.Branch.select (branchable=app.branchable)),
                                       '-is_default', 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != app.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    if app.data.has_key ('screenshot'):
        page.add_screenshot (app.data['screenshot'])

    sep = False
    try:
        desc = app.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    rels = pulse.db.SetModule.get_related (pred=app.parent)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = [pulse.html.Link(obj.pulse_url + '#programs', obj.title) for obj in sets]
        span = pulse.html.Span (*span)
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    page.add_fact (pulse.utils.gettext ('Module'), pulse.html.Link (app.parent))

    if sep:
        page.add_fact_divider ()
    
    page.add_fact (pulse.utils.gettext ('Location'),
                   checkout.get_location (app.scm_dir, app.scm_file))

    if app.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (app.mod_datetime.strftime('%Y-%m-%d %T'))
        if app.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (app.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    # Developers
    box = pulse.pages.mod.get_developers_box (app.parent)
    page.add_sidebar_content (box)

    # Documentation
    rels = pulse.db.Documentation.get_related (subj=app)
    box = pulse.html.InfoBox (pulse.utils.gettext ('Documentation'))
    page.add_content (box)
    if len(rels) > 0:
        docs = pulse.utils.attrsorted ([rel.pred for rel in rels], 'title')
        for doc in docs:
            lbox = box.add_link_box (doc)
            res = doc.select_children (u'Translation')
            lbox.add_fact (None, pulse.utils.gettext ('%i translations') % res.count())
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documentation') ))
