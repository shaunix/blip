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
import pulse.graphs
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
            kw['title'] = pulse.utils.gettext ('Document Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the document %s') % path[3],
                **kw)
            page.output(fd=fd)
            return 404

        doc = branchable.default
        if doc == None:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Default Branch Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch for the document %s') % path[3],
                **kw)
            page.output(fd=fd)
            return 404

    elif len(path) == 5:
        docs = db.Branch.objects.filter (ident=('/' + '/'.join(path)))
        try:
            doc = docs[0]
        except IndexError:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Document Not Found')
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the document %s') % (path[4], path[3]),
                **kw)
            page.output(fd=fd)
            return 404
    else:
        # FIXME: redirect to /set or something
        pass

    if query.has_key ('ajax'):
        return output_ajax (doc, path, query, http, fd)
    else:
        return output_doc (doc, path, query, http, fd)


def output_doc (doc, path=[], query=[], http=True, fd=None):
    page = pulse.html.RecordPage (doc, http=http)
    checkout = pulse.scm.Checkout.from_record (doc, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(doc.branchable.branches.all()), 'scm_branch')
    if len(branches) > 1:
        for b in branches:
            if b.ident != doc.ident:
                page.add_sublink (b.pulse_url, b.ident.split('/')[-1])
            else:
                page.add_sublink (None, b.ident.split('/')[-1])

    sep = False
    try:
        desc = doc.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    rels = db.SetModule.get_related (pred=doc.parent)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(rel.subj.pulse_url + '/doc', rel.subj.title) for rel in rels])
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    page.add_fact (pulse.utils.gettext ('Module'), pulse.html.Link (doc.parent))

    if sep: page.add_fact_sep ()
    
    page.add_fact (pulse.utils.gettext ('Location'), checkout.get_location (doc.scm_dir, doc.scm_file))

    if doc.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (str(doc.mod_datetime))
        if doc.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (doc.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    columns.add_to_column (0, box)
    rels = db.DocumentEntity.get_related (subj=doc)
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
            if rel.author:
                lbox.add_badge ('author')
            if rel.editor:
                lbox.add_badge ('editor')
            if rel.publisher:
                lbox.add_badge ('publisher')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))

    # Files
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    pad = pulse.html.PaddingBox ()
    box.add_content (pad)
    columns.add_to_column (0, box)
    graph = pulse.html.Graph ('/'.join(doc.ident.split('/')[1:] + ['commits.png']))
    graphdir = os.path.join (*([pulse.config.web_graphs_dir] + doc.ident.split('/')[1:]))
    graphdata = pulse.graphs.load_graph_data (os.path.join (graphdir, 'commits.imap'))
    for i in range(len(graphdata)):
        datum = graphdata[i]
        ago = len(graphdata) - i - 1
        if ago > 0:
            cmt = pulse.utils.gettext ('%i weeks ago: %i commits') % (ago, datum[1])
        else:
            cmt = pulse.utils.gettext ('this week: %i commits') % datum[1]
        graph.add_comment (datum[0], cmt)
    pad.add_content (graph)
    div = pulse.html.Div (id='actfiles')
    pad.add_content (div)
    xmlfiles = doc.data.get('xmlfiles', [])
    if len(xmlfiles) > 10:
        jslink = 'javascript:replace_content(\'actfiles\', '
        jslink += '\'%s%s?ajax=activity\'' % (pulse.config.web_root, doc.ident[1:])
        jslink += ')'
        div.add_content (pulse.html.Link (jslink,
                                          pulse.utils.gettext ('View all %i files') % len(xmlfiles)))
    else:
        div.add_content (get_activity (doc, xmlfiles))

    cont = pulse.html.ContainerBox()
    cont.set_title (pulse.utils.gettext ('History'))
    pad.add_content (cont)
    revs = db.Revision.select_revisions (branch=doc, filename=True)
    cnt = revs.count()
    dl = pulse.html.DefinitionList()
    cont.add_content (dl)
    seen = []
    done = False
    i = 0
    while not done:
        revlist = revs[i : i + 20]
        for rev in revlist:
            if rev.revision in seen: continue
            seen.append (rev.revision)
            span = pulse.html.Span (divider=pulse.html.SPACE)
            span.add_content (rev.revision)
            span.add_content ('on')
            span.add_content (str(rev.datetime))
            span.add_content ('by')
            if not rev.person_id in people_cache:
                people_cache[rev.person_id] = rev.person
            person = people_cache[rev.person_id]
            span.add_content (pulse.html.Link (person))
            dl.add_term (span)
            dl.add_entry (pulse.html.RevisionPopupLink (rev.comment))
            if len(seen) >= 10:
                done = True
                break
        if len(revlist) < 20:
            break
        i += 20

    # Translations
    box = pulse.html.InfoBox ('translations', pulse.utils.gettext ('Translations'))
    columns.add_to_column (1, box)
    cont = pulse.html.ContainerBox ()
    cont.set_id ('po')
    box.add_content (cont)
    pad = pulse.html.PaddingBox ()
    cont.add_content (pad)

    potlst = doc.ident.split('/')[1:] + [doc.ident.split('/')[-2] + '.pot']
    poturl = pulse.config.l10n_root + '/'.join (potlst)
    potfile = os.path.join (*potlst)
    of = db.OutputFile.objects.filter (type='l10n', filename=potfile)
    try:
        of = of[0]
        linkspan = pulse.html.Span (divider=pulse.html.SPACE)
        pad.add_content (linkspan)
        linkspan.add_content (pulse.html.Link (poturl,
                                               pulse.utils.gettext ('POT file'),
                                               icon='download' ))
        # FIXME: i18n reordering
        linkspan.add_content (pulse.utils.gettext ('(%i messages)') % of.statistic)
        linkspan.add_content (pulse.utils.gettext ('on %s') % str(of.datetime))
    except IndexError:
        pad.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                               pulse.utils.gettext ('No POT file') ))

    translations = doc.select_children ('Translation')
    translations = pulse.utils.attrsorted (list(translations), 'title')
    if len(translations) == 0:
        pad.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                               pulse.utils.gettext ('No translations') ))
    else:
        cont.set_sortable_tag ('tr')
        cont.set_sortable_class ('po')
        cont.add_sort_link ('title', pulse.utils.gettext ('lang'), False)
        cont.add_sort_link ('percent', pulse.utils.gettext ('percent'))
        cont.add_sort_link ('img', pulse.utils.gettext ('images'))
        grid = pulse.html.GridBox ()
        pad.add_content (grid)
        for translation in translations:
            stat = db.Statistic.select_statistic (translation, 'Messages')
            span = pulse.html.Span (translation.scm_file[:-3])
            span.add_class ('title')
            row = [span]
            percent = 0
            try:
                stat = stat[0]
                untranslated = stat.total - stat.stat1 - stat.stat2
                percent = math.floor (100 * (float(stat.stat1) / stat.total))
                span = pulse.html.Span ('%i%%' % percent)
                span.add_class ('percent')
                row.append (span)

                row.append (pulse.utils.gettext ('%i.%i.%i') %
                            (stat.stat1, stat.stat2, untranslated))
                imgstat = db.Statistic.select_statistic (translation, 'ImageMessages')
                try:
                    imgstat = imgstat[0]
                    span = pulse.html.Span(str(imgstat.stat1))
                    span.add_class ('img')
                    fspan = pulse.html.Span (span, '/', str(imgstat.total), divider=pulse.html.SPACE)
                    row.append (fspan)
                except IndexError:
                    pass
            except IndexError:
                pass
            idx = grid.add_row (*row)
            grid.add_row_class (idx, 'po')
            if percent >= 80:
                grid.add_row_class (idx, 'po80')
            elif percent >= 50:
                grid.add_row_class (idx, 'po50')

    page.output(fd=fd)

    return 0


def output_ajax (doc, path, query, http, fd):
    page = pulse.html.Fragment ()
    xmlfiles = doc.data.get('xmlfiles', [])
    page.add_content (get_activity (doc, xmlfiles))
    page.output(fd=fd)
    return 0

def get_activity (doc, xmlfiles):
    cont = pulse.html.ContainerBox()
    cont.set_title (pulse.utils.gettext ('Files'))
    dl = pulse.html.DefinitionList()
    cont.add_content (dl)
    if len(xmlfiles) > 1:
        cont.set_sortable_tag ('dt')
        cont.set_sortable_class ('actfile')
        cont.add_sort_link ('title', pulse.utils.gettext ('name'), False)
        cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    for xmlfile in xmlfiles:
        span = pulse.html.Span (xmlfile)
        span.add_class ('title')
        dl.add_term (span, class_name='actfile')
        commit = db.Revision.get_last_revision (branch=doc, filename=xmlfile)
        if commit != None:
            span = pulse.html.Span(divider=pulse.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            mspan = pulse.html.Span()
            mspan.add_content (str(commit.datetime))
            mspan.add_class ('mtime')
            span.add_content (mspan)
            span.add_content (' by ')
            if not commit.person_id in people_cache:
                people_cache[commit.person_id] = commit.person
            person = people_cache[commit.person_id]
            span.add_content (pulse.html.Link (person))
            dl.add_entry (span)
    return cont

