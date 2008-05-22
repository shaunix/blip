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
    person = None
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    if len(path) == 1:
        return output_top (**kw)
    person = db.Entity.objects.filter (ident=('/' + '/'.join(path)), type='Person')
    try:
        person = person[0]
    except IndexError:
        person = None
    if person == None:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Person Not Found')
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the person %s') % '/'.join(path[1:]),
            **kw)
        page.output(fd=fd)
        return 404

    if query.get('ajax', None) == 'commits':
        return output_ajax_commits (person, **kw)
    else:
        return output_person (person, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.InfoBox ('people', pulse.utils.gettext ('People'))
    people = db.Entity.objects.filter (type='Person').order_by ('-mod_score')
    box.add_content (pulse.html.Div (pulse.utils.gettext ('These people deserve a beer:')))
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    for person in people[:12]:
        bl.add_item (pulse.html.Link (person))
    return box


def output_top (**kw):
    page = pulse.html.Page (http=kw.get('http', True))
    page.set_title (pulse.utils.gettext ('People'))
    people = db.Entity.objects.filter (type='Person').order_by ('-mod_score')
    page.add_content(pulse.html.Div(pulse.utils.gettext('42 most active people:')))
    for person in people[:42]:
        lbox = pulse.html.LinkBox (person)
        lbox.add_fact (pulse.utils.gettext ('score'), str(person.mod_score))
        lbox.add_graph (pulse.config.graphs_root
                        + '/'.join(person.ident.split('/')[1:] + ['commits.png']))
        page.add_content (lbox)
    page.output (fd=kw.get('fd'))


def output_person (person, **kw):
    page = pulse.html.RecordPage (person, http=kw.get('http', True))

    if person.nick != None:
        page.add_fact (pulse.utils.gettext ('Nick'), person.nick)
        page.add_fact_sep ()
    if person.email != None:
        page.add_fact (pulse.utils.gettext ('Email'),
                       pulse.html.Link ('mailto:' + person.email, person.email))
    if person.web != None:
        page.add_fact (pulse.utils.gettext ('Website'), pulse.html.Link (person.web))
    page.add_fact (pulse.utils.gettext ('Score'), str(person.mod_score))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Activity
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    columns.add_to_column (0, box)
    of = db.OutputFile.objects.filter (type='graphs', ident=person.ident, filename='commits.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, person.pulse_url)
        box.add_content (graph)
    except IndexError:
        pass

    revs = db.Revision.select_revisions (person=person)
    cnt = revs.count()
    revs = revs[:10]
    div = get_commits_div (person, revs,
                           pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    box.add_content (div)

    # Modules and Documents
    mods = db.Branch.objects.filter (type='Module', module_entity_preds__pred=person)
    mods = pulse.utils.attrsorted (list(mods), 'title')
    if len(mods) > 0:
        modbox = pulse.html.InfoBox ('modules', pulse.utils.gettext ('Modules'))
        columns.add_to_column (1, modbox)
        brs = []
        for mod in mods:
            if mod.branchable_id in brs:
                continue
            brs.append (mod.branchable_id)
            modbox.add_link_box (mod)

    docs = db.Branch.objects.filter (type='Document', document_entity_preds__pred=person)
    docs = pulse.utils.attrsorted (list(docs), 'title')
    if len(docs) > 0:
        docbox = pulse.html.InfoBox ('documents', pulse.utils.gettext ('Documents'))
        columns.add_to_column (1, docbox)
        brs = []
        for doc in docs:
            if doc.branchable_id in brs:
                continue
            brs.append (doc.branchable_id)
            docbox.add_link_box (doc)

    page.output(fd=kw.get('fd'))

    return 0


def output_ajax_commits (person, **kw):
    page = pulse.html.Fragment (http=kw.get('http', True))
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
    div = get_commits_div (person, revs, title)
    page.add_content (div)
    page.output(fd=kw.get('fd'))
    return 0


def get_commits_div (person, revs, title):
    div = pulse.html.Div (id='commits')
    div.add_content (title)
    dl = pulse.html.DefinitionList()
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
