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
import pulse.db
import pulse.graphs
import pulse.html
import pulse.scm
import pulse.utils

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 4:
        modules = pulse.db.Resource.selectBy (ident=('/' + '/'.join(path)))
        if modules.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Document Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the document %s') % path[3],
                **kw)
            page.output(fd=fd)
            return 404
        else:
            doc = modules[0].default_branch
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
        docs = pulse.db.Branch.selectBy (ident=('/' + '/'.join(path)))
        if docs.count() == 0:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Document Not Found')
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the document %s') % (path[4], path[3]),
                **kw)
            page.output(fd=fd)
            return 404
        else:
            doc = docs[0]
    else:
        # FIXME: redirect to /set or something
        pass

    if query.has_key ('ajax'):
        return output_ajax (doc, path, query, http, fd)
    else:
        return output_doc (doc, path, query, http, fd)


def output_doc (doc, path=[], query=[], http=True, fd=None):
    page = pulse.html.ResourcePage (doc, http=http)
    checkout = pulse.scm.Checkout.from_record (doc.parent, checkout=False, update=False)

    branches = pulse.db.Branch.selectBy (resource=doc.resource)
    if branches.count() > 1:
        for b in pulse.utils.attrsorted (branches[0:], 'scm_branch'):
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

    rels = pulse.db.RecordBranchRelation.selectBy (pred=doc.parent, verb='SetModule')
    if rels.count() > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(rel.subj.pulse_url + '/doc', rel.subj.title) for rel in rels])
        span.set_divider (span.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    page.add_fact (pulse.utils.gettext ('Module'), pulse.html.Link (doc.parent))

    if sep: page.add_fact_sep ()
    
    page.add_fact (pulse.utils.gettext ('Location'), checkout.get_location (doc.scm_dir, doc.scm_file))

    if doc.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.Span.SPACE)
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
    columns.add_content (0, box)
    authors = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentAuthor')
    editors = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentEditor')
    credits = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentCredit')
    maints = pulse.db.BranchEntityRelation.selectBy (subj=doc, verb='DocumentMaintainer')
    people = {}
    for t, l in (('author', authors), ('editor', editors), ('credit', credits), ('maint', maints)):
        for cr in l:
            people.setdefault (cr.pred, [])
            people[cr.pred].append(t)
    if len(people) > 0:
        lcont = pulse.html.LinkBoxContainer()
        box.add_content (lcont)
        for person in pulse.utils.attrsorted (people.keys(), 'title'):
            lbox = lcont.add_link_box (person)
            badges = people[person]
            if 'maint' in badges:
                lbox.add_badge ('maintainer')
            if 'author' in badges:
                lbox.add_badge ('author')
            if 'editor' in badges:
                lbox.add_badge ('editor')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))

    # Files
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    columns.add_content (0, box)
    graph = pulse.html.Graph ('/'.join(doc.ident.split('/')[1:] + ['commits.png']))
    graphdir = os.path.join (*([pulse.config.webdir, 'var', 'graph'] + doc.ident.split('/')[1:]))
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
    div = pulse.html.Div (id='actfiles')
    box.add_content (div)
    xmlfiles = doc.data.get('xmlfiles', [])
    if len(xmlfiles) > 10:
        jslink = 'javascript:replace_content(\'actfiles\', '
        jslink += '\'%s%s?ajax=activity\'' % (pulse.config.webroot, doc.ident[1:])
        jslink += ')'
        div.add_content (pulse.html.Link (jslink,
                                          pulse.utils.gettext ('View all %i files') % len(xmlfiles)))
    else:
        div.add_content (get_activity (doc, xmlfiles))

    # Translations
    box = pulse.html.InfoBox ('translations', pulse.utils.gettext ('Translations'))
    columns.add_content (1, box)
    vbox = pulse.html.VBox()
    box.add_content (vbox)

    potlst = ['var', 'l10n'] + doc.ident.split('/')[1:] + [doc.ident.split('/')[-2] + '.pot']
    poturl = pulse.config.varroot + '/'.join (potlst[1:])
    potfile = os.path.join (*potlst)
    vf = pulse.db.VarFile.selectBy (filename=potfile)
    if vf.count() > 0:
        linkspan = pulse.html.Span (divider=pulse.html.Span.SPACE)
        vbox.add_content (linkspan)
        vf = vf[0]
        linkspan.add_content (pulse.html.Link (poturl,
                                               pulse.utils.gettext ('POT file'),
                                               icon='download' ))
        # FIXME: i18n reordering
        linkspan.add_content (pulse.utils.gettext ('(%i messages)') % vf.statistic)
        linkspan.add_content (pulse.utils.gettext ('on %s') % str(vf.datetime))
    else:
        vbox.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                               pulse.utils.gettext ('No POT file') ))

    translations = pulse.db.Branch.selectBy (parent=doc, type='Translation')
    translations = pulse.utils.attrsorted (list(translations), 'title')
    if len(translations) == 0:
        vbox.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                               pulse.utils.gettext ('No translations') ))
    else:
        slinks = pulse.html.SortLinkComponent ('tr', 'po')
        slinks.add_sort_link ('title', pulse.utils.gettext ('lang'), False)
        slinks.add_sort_link ('percent', pulse.utils.gettext ('percent'))
        slinks.add_sort_link ('img', pulse.utils.gettext ('images'))
        vbox.add_content (slinks)
        grid = pulse.html.GridBox ()
        vbox.add_content (grid)
        for translation in translations:
            stat = pulse.db.Statistic.select ((pulse.db.Statistic.q.branchID == translation.id) &
                                              (pulse.db.Statistic.q.type == 'Messages'),
                                              orderBy='-daynum')
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
                imgstat = pulse.db.Statistic.select ((pulse.db.Statistic.q.branchID == translation.id) &
                                                     (pulse.db.Statistic.q.type == 'ImageMessages'),
                                                     orderBy='-daynum')
                if imgstat.count() > 0:
                    imgstat = imgstat[0]
                    span = pulse.html.Span(str(imgstat.stat1))
                    span.add_class ('img')
                    fspan = pulse.html.Span (span, '/', str(imgstat.total), divider=pulse.html.Span.SPACE)
                    row.append (fspan)
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
    page = pulse.html.HttpContainer ()
    xmlfiles = doc.data.get('xmlfiles', [])
    page.add_content (get_activity (doc, xmlfiles))
    page.output(fd=fd)
    return 0

def get_activity (doc, xmlfiles):
    lcont = pulse.html.LinkBoxContainer()
    if len(xmlfiles) > 1:
        lcont.set_sort_link_class ('actfile')
        lcont.add_sort_link ('title', pulse.utils.gettext ('name'), False)
        lcont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    for xmlfile in xmlfiles:
        lbox = lcont.add_link_box (None, xmlfile)
        lbox.add_class ('actfile')
        lbox.set_show_icon (False)
        commit = pulse.db.Revision.select ((pulse.db.Revision.q.branchID == doc.id) &
                                           (pulse.db.Revision.q.filename == xmlfile),
                                           orderBy='-datetime')
        try:
            commit = commit[0]
            span = pulse.html.Span(divider=pulse.html.Span.SPACE)
            # FIXME: i18n, word order, but we want to link person
            mspan = pulse.html.Span()
            mspan.add_content (str(commit.datetime))
            mspan.add_class ('mtime')
            span.add_content (mspan)
            span.add_content (' by ')
            span.add_content (pulse.html.Link (commit.person))
            lbox.add_fact (None, span)
        except IndexError:
            pass
    return lcont
