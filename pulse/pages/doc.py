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

"""Output information about documents"""

import datetime
import math
import os

import pulse.config
import pulse.graphs
import pulse.html
import pulse.models as db
import pulse.scm
import pulse.utils

people_cache = {}

def main (path, query, http=True, fd=None):
    """Output information about documents"""
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
                pulse.utils.gettext ('Pulse could not find a default branch'
                                     ' for the document %s')
                % path[3],
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
                pulse.utils.gettext ('Pulse could not find the branch %s of the document %s')
                % (path[4], path[3]),
                **kw)
            page.output(fd=fd)
            return 404
    else:
        # FIXME: redirect to /set or something
        pass

    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    if query.get('ajax', None) == 'commits':
        return output_ajax_commits (doc, **kw)
    elif query.get('ajax', None) == 'figures':
        return output_ajax_figures (doc, **kw)
    elif query.get('ajax', None) == 'graphmap':
        return output_ajax_graphmap (doc, **kw)
    elif query.get('ajax', None) == 'xmlfiles':
        return output_ajax_xmlfiles (doc, **kw)
    else:
        return output_doc (doc, **kw)


def output_doc (doc, **kw):
    """Output information about a document"""
    page = pulse.html.RecordPage (doc, http=kw.get('http', True))
    checkout = pulse.scm.Checkout.from_record (doc, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(doc.branchable.branches.all()), 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != doc.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    if doc.data.has_key ('screenshot'):
        page.add_screenshot (doc.data['screenshot'])

    if doc.error != None:
        page.add_fact (pulse.utils.gettext ('Error'),
                       pulse.html.AdmonBox (pulse.html.AdmonBox.error, doc.error))
        page.add_fact_sep ()

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
        span = pulse.html.Span (*[pulse.html.Link(rset.pulse_url + '/doc', rset.title)
                                  for rset in sets])
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    page.add_fact (pulse.utils.gettext ('Module'), pulse.html.Link (doc.parent))

    rels = db.Documentation.get_related (pred=doc)
    if len(rels) > 0:
        objs = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(obj) for obj in objs])
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Describes'), span)
        sep = True

    if sep:
        page.add_fact_sep ()
    
    page.add_fact (pulse.utils.gettext ('Location'),
                   checkout.get_location (doc.scm_dir, doc.scm_file))

    if doc.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (doc.mod_datetime.strftime('%Y-%m-%d %T'))
        if doc.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (doc.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    page.add_fact_sep ()
    page.add_fact (pulse.utils.gettext ('Score'), str(doc.mod_score))

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

    # Activity
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    columns.add_to_column (0, box)
    of = db.OutputFile.objects.filter (type='graphs', ident=doc.ident, filename='commits-0.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, doc.pulse_url)
        box.add_content (graph)
    except IndexError:
        pass

    div = pulse.html.AjaxBox (doc.pulse_url + '?ajax=commits')
    box.add_content (div)

    # Files
    box = pulse.html.InfoBox ('files', pulse.utils.gettext ('Files'))
    columns.add_to_column (0, box)
    xmlfiles = doc.data.get('xmlfiles', [])
    if len(xmlfiles) > 10:
        div = pulse.html.AjaxBox (doc.pulse_url + '?ajax=xmlfiles')
    else:
        div = get_xmlfiles (doc, xmlfiles)
    box.add_content (div)

    # Release Info
    box = pulse.html.InfoBox ('release', pulse.utils.gettext ('Release Info'))
    columns.add_to_column (1, box)
    facts = pulse.html.FactList ()
    facts.add_term ('Status:')
    facts.add_entry (doc.data.get ('status', 'none'))
    box.add_content (facts)

    # Figures
    figures = doc.data.get('figures', {})
    if len(figures) > 0:
        box = pulse.html.InfoBox ('figures', pulse.utils.gettext ('Figures'))
        columns.add_to_column (1, box)
        if len(figures) > 10:
            div = pulse.html.AjaxBox (doc.pulse_url + '?ajax=figures')
        else:
            div = get_figures (doc, figures)
        box.add_content (div)

    # Translations
    box = pulse.html.InfoBox ('translations', pulse.utils.gettext ('Translations'))
    columns.add_to_column (1, box)
    cont = pulse.html.ContainerBox ()
    cont.set_id ('po')
    box.add_content (cont)
    pad = pulse.html.PaddingBox ()
    cont.add_content (pad)

    of = db.OutputFile.objects.filter (type='l10n', ident=doc.ident,
                                       filename=(doc.ident.split('/')[-2] + '.pot'))
    try:
        of = of[0]
        linkspan = pulse.html.Span (divider=pulse.html.SPACE)
        pad.add_content (linkspan)
        linkspan.add_content (pulse.html.Link (of.pulse_url,
                                               pulse.utils.gettext ('POT file'),
                                               icon='download' ))
        # FIXME: i18n reordering
        linkspan.add_content (pulse.utils.gettext ('(%i messages)') % of.statistic)
        linkspan.add_content (pulse.utils.gettext ('on %s') % of.datetime.strftime('%Y-%m-%d %T'))
    except IndexError:
        pad.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                               pulse.utils.gettext ('No POT file') ))

    translations = db.Branch.select_with_statistic (['Messages', 'ImageMessages'],
                                                    type='Translation', parent=doc)
    translations = pulse.utils.attrsorted (list(translations), 'title')
    if len(translations) == 0:
        pad.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                               pulse.utils.gettext ('No translations') ))
    else:
        cont.set_sortable_tag ('tr')
        cont.set_sortable_class ('po')
        cont.add_sort_link ('title', pulse.utils.gettext ('lang'), 1)
        cont.add_sort_link ('percent', pulse.utils.gettext ('percent'))
        cont.add_sort_link ('img', pulse.utils.gettext ('images'))
        grid = pulse.html.GridBox ()
        pad.add_content (grid)
        for translation in translations:
            span = pulse.html.Span (translation.scm_file[:-3])
            span.add_class ('title')
            link = pulse.html.Link (translation.pulse_url, span)
            row = [link]
            percent = 0
            stat1 = translation.Messages_stat1
            stat2 = translation.Messages_stat2
            total = translation.Messages_total
            untranslated = total - stat1 - stat2
            percent = math.floor (100 * (float(stat1) / total))
            span = pulse.html.Span ('%i%%' % percent)
            span.add_class ('percent')
            row.append (span)

            row.append (pulse.utils.gettext ('%i.%i.%i') %
                        (stat1, stat2, untranslated))
            istat1 = translation.ImageMessages_stat1
            itotal = translation.ImageMessages_total
            span = pulse.html.Span(str(istat1))
            span.add_class ('img')
            fspan = pulse.html.Span (span, '/', str(itotal), divider=pulse.html.SPACE)
            row.append (fspan)
            idx = grid.add_row (*row)
            grid.add_row_class (idx, 'po')
            if percent >= 80:
                grid.add_row_class (idx, 'po80')
            elif percent >= 50:
                grid.add_row_class (idx, 'po50')

    page.output(fd=kw.get('fd'))

    return 0


def output_ajax_figures (doc, **kw):
    page = pulse.html.Fragment (http=kw.get('http', True))
    figures = doc.data.get('figures', {})
    page.add_content (get_figures (doc, figures))
    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_graphmap (doc, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    id = query.get('id')
    num = query.get('num')
    filename = query.get('filename')
    
    of = db.OutputFile.objects.filter (type='graphs', ident=doc.ident, filename=filename)
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, doc.pulse_url,
                                                 count=int(id), num=int(num), map_only=True)
        page.add_content (graph)
    except IndexError:
        pass
    
    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_xmlfiles (doc, **kw):
    page = pulse.html.Fragment (http=kw.get('http', True))
    xmlfiles = doc.data.get('xmlfiles', [])
    page.add_content (get_xmlfiles (doc, xmlfiles))
    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_commits (doc, **kw):
    page = pulse.html.Fragment (http=kw.get('http', True))
    query = kw.get('query', {})
    weeknum = query.get('weeknum', None)
    files = [os.path.join (doc.scm_dir, f) for f in doc.data.get ('xmlfiles', [])]
    if weeknum != None:
        weeknum = int(weeknum)
        thisweek = pulse.utils.weeknum (datetime.datetime.now())
        ago = thisweek - weeknum
        revs = db.Revision.select_revisions (branch=doc.parent, files=files, weeknum=weeknum)
        cnt = revs.count()
        revs = revs[:20]
    else:
        revs = db.Revision.select_revisions (branch=doc.parent, files=files)
        cnt = revs.count()
        revs = revs[:10]
    if weeknum == None:
        title = (pulse.utils.gettext('Showing %i of %i commits:')
                 % (len(revs), cnt))
    elif ago == 0:
        title = (pulse.utils.gettext('Showing %i of %i commits from this week:')
                 % (len(revs), cnt))
    elif ago == 1:
        title = (pulse.utils.gettext('Showing %i of %i commits from last week:')
                 % (len(revs), cnt))
    else:
        title = (pulse.utils.gettext('Showing %i of %i commits from %i weeks ago:')
                 % (len(revs), cnt, ago))
    div = get_commits_div (doc, revs, title)
    page.add_content (div)
    page.output(fd=kw.get('fd'))
    return 0


def get_xmlfiles (doc, xmlfiles):
    cont = pulse.html.ContainerBox()
    cont.set_id ('xmlfiles')
    dl = pulse.html.DefinitionList()
    cont.add_content (dl)
    if len(xmlfiles) > 1:
        cont.set_sortable_tag ('dt')
        cont.add_sort_link ('title', pulse.utils.gettext ('name'), 1)
        cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    for xmlfile in xmlfiles:
        span = pulse.html.Span (xmlfile)
        span.add_class ('title')
        dl.add_term (span, classname='xmlfiles')
        files = [os.path.join (doc.scm_dir, xmlfile)]
        commit = db.Revision.get_last_revision (branch=doc.parent, files=files)
        if commit != None:
            span = pulse.html.Span(divider=pulse.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            mspan = pulse.html.Span()
            mspan.add_content (commit.datetime.strftime('%Y-%m-%d %T'))
            mspan.add_class ('mtime')
            span.add_content (mspan)
            span.add_content (' by ')
            if not commit.person_id in people_cache:
                people_cache[commit.person_id] = commit.person
            person = people_cache[commit.person_id]
            span.add_content (pulse.html.Link (person))
            dl.add_entry (span)
    return cont


def get_figures (doc, figures):
    cont = pulse.html.ContainerBox()
    cont.set_id ('figures')
    cont.set_sortable_tag ('dt')
    cont.add_sort_link ('title', pulse.utils.gettext ('name'), 1)
    cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    ofs = db.OutputFile.objects.filter (type='figures', ident=doc.ident, subdir='C')
    ofs_by_source = {}
    for of in ofs:
        ofs_by_source[of.source] = of
    dl = pulse.html.DefinitionList ()
    cont.add_content (dl)
    for figure in sorted(figures.keys()):
        of = ofs_by_source.get(figure)
        if of:
            span = pulse.html.Span (pulse.html.Link (of.pulse_url, figure, classname='zoom'))
            span.add_class ('title')
            dl.add_term (span, classname='figures')
            files = [os.path.join (doc.scm_dir, of.source)]
            commit = db.Revision.get_last_revision (branch=doc.parent, files=files)
            if commit != None:
                span = pulse.html.Span(divider=pulse.html.SPACE)
                # FIXME: i18n, word order, but we want to link person
                mspan = pulse.html.Span()
                mspan.add_content (commit.datetime.strftime('%Y-%m-%d %T'))
                mspan.add_class ('mtime')
                span.add_content (mspan)
                span.add_content (' by ')
                if not commit.person_id in people_cache:
                    people_cache[commit.person_id] = commit.person
                person = people_cache[commit.person_id]
                span.add_content (pulse.html.Link (person))
                dl.add_entry (span)
            if figures[figure].get('comment', '') != '':
                dl.add_entry (pulse.html.EllipsizedLabel (figures[figure]['comment'], 80),
                              classname='desc')
        else:
            dl.add_term (figure)
    return cont


def get_commits_div (doc, revs, title):
    div = pulse.html.Div (id='commits')
    div.add_content (title)
    dl = pulse.html.DefinitionList()
    div.add_content (dl)
    curweek = None
    for rev in revs:
        if curweek != None and curweek != rev.weeknum:
            dl.add_divider ()
        curweek = rev.weeknum
        span = pulse.html.Span (divider=pulse.html.SPACE)
        span.add_content (rev.display_revision (doc.parent))
        span.add_content ('on')
        span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
        span.add_content ('by')
        if not rev.person_id in people_cache:
            people_cache[rev.person_id] = rev.person
        person = people_cache[rev.person_id]
        span.add_content (pulse.html.Link (person))
        dl.add_term (span)
        dl.add_entry (pulse.html.PopupLink.from_revision (rev, branch=doc.parent))
    return div
