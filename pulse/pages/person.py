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

import os

import pulse.config
import pulse.graphs
import pulse.html
import pulse.models as db
import pulse.scm
import pulse.utils

def main (path=[], query={}, http=True, fd=None):
    person = None
    if len(path) == 1:
        return output_top (path, query, http, fd)
    if len(path) == 3:
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

    return output_person (person, path, query, http, fd)


def output_top (path=[], query={}, http=True, fd=None):
    page = pulse.html.Page (http=http)
    page.set_title (pulse.utils.gettext ('People'))
    people = db.Entity.objects.filter (type='Person').order_by ('-mod_score')
    page.add_content(pulse.html.Div(pulse.utils.gettext('42 most active people:')))
    for person in people[:42]:
        lbox = pulse.html.LinkBox (person)
        lbox.add_fact (pulse.utils.gettext ('score'), str(person.mod_score))
        lbox.add_graph ('/'.join(person.ident.split('/')[1:] + ['commits.png']))
        page.add_content (lbox)
    page.output (fd=fd)


def output_person (person, path=[], query=[], http=True, fd=None):
    page = pulse.html.RecordPage (person, http=http)

    if person.nick != None:
        page.add_fact (pulse.utils.gettext ('Nick'), person.nick)
        page.add_fact_sep ()
    if person.email != None:
        page.add_fact (pulse.utils.gettext ('Email'),
                       pulse.html.Link ('mailto:' + person.email, person.email))
    if person.web != None:
        page.add_fact (pulse.utils.gettext ('Website'), pulse.html.Link (person.web))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Activity
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    columns.add_to_column (0, box)
    graph = pulse.html.Graph ('/'.join(person.ident.split('/')[1:] + ['commits.png']))
    graphdir = os.path.join (*([pulse.config.webdir, 'var', 'graph'] + person.ident.split('/')[1:]))
    graphdata = pulse.graphs.load_graph_data (os.path.join (graphdir, 'commits.imap'))
    for i in range(len(graphdata)):
        datum = graphdata[i]
        ago = len(graphdata) - i - 1
        if ago > 0:
            cmt = pulse.utils.gettext ('%i weeks ago: %i commits') % (ago, datum[1])
        else:
            cmt = pulse.utils.gettext ('this week: %i commits') % datum[1]
        graph.add_comment (datum[0], cmt)
    box.add_content (graph)
    revs = db.Revision.select_revisions (person=person, filename=None)
    cnt = revs.count()
    box.add_content ('Showing %i of %i commits:' % (min(10, cnt), cnt))
    dl = pulse.html.DefinitionList()
    box.add_content (dl)
    for rev in revs[:10]:
        # FIXME: i18n word order
        span = pulse.html.Span (divider=pulse.html.SPACE)
        span.add_content (pulse.html.Link (rev.branch.pulse_url, rev.branch.branch_module))
        span.add_content ('on')
        span.add_content (str(rev.datetime))
        dl.add_term (span)
        comment = rev.comment
        dl.add_entry (pulse.html.RevisionPopupLink (rev.comment))

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

    page.output(fd=fd)

    return 0
