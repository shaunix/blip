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
import pulse.db
import pulse.graphs
import pulse.html
import pulse.scm
import pulse.utils

def main (response, path, query):
    """Output information about documents"""
    ident = u'/' + u'/'.join(path)
    if len(path) == 4:
        branches = list(pulse.db.Branch.select (branchable=ident))
        if len(branches) == 0:
            page = pulse.html.PageNotFound ( 
               pulse.utils.gettext ('Pulse could not find the document %s') % path[3],
               title=pulse.utils.gettext ('Document Not Found'))
            response.set_contents (page)
            return

        doc = [branch for branch in branches if branch.is_default]
        if len(doc) == 0:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch'
                                     ' for the document %s')
                % path[3],
                title=pulse.utils.gettext ('Default Branch Not Found'))
            response.set_contents(page)
            return
        doc = doc[0]
    elif len(path) == 5:
        doc = pulse.db.Branch.get (ident)
        if doc == None:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the document %s')
                % (path[4], path[3]),
                title=pulse.utils.gettext ('Document Not Found'))
            response.set_contents (page)
            return
    else:
        # FIXME: redirect to /set or something
        pass

    kw = {'path' : path, 'query' : query}
    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, doc, **kw)
    elif query.get('ajax', None) == 'commits':
        output_ajax_commits (response, doc, **kw)
    elif query.get('ajax', None) == 'figures':
        output_ajax_figures (response, doc, **kw)
    elif query.get('ajax', None) == 'graphmap':
        output_ajax_graphmap (response, doc, **kw)
    elif query.get('ajax', None) == 'xmlfiles':
        output_ajax_xmlfiles (response, doc, **kw)
    else:
        output_doc (response, doc, **kw)


def output_doc (response, doc, **kw):
    """Output information about a document"""
    page = pulse.html.Page (doc)
    response.set_contents (page)

    branches = pulse.utils.attrsorted (list(pulse.db.Branch.select (branchable=doc.branchable)),
                                       '-is_default', 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != doc.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    if doc.data.has_key ('screenshot'):
        page.add_screenshot (doc.data['screenshot'])

    page.add_tab ('info', pulse.utils.gettext ('Info'))
    box = get_info_tab (doc, **kw)
    page.add_to_tab ('info', box)

    # Release Info
    box = pulse.html.SidebarBox (pulse.utils.gettext ('Release Info'))
    page.add_sidebar_content (box)
    facts = pulse.html.FactList ()
    facts.add_term ('Status:')
    facts.add_entry (doc.data.get ('status', 'none'))
    for link in doc.data.get ('releaselinks', []):
        if link[0] == 'bug':
            facts.add_term (pulse.utils.gettext ('Bug:'))
        elif link[0] == 'planning':
            facts.add_term (pulse.utils.gettext ('Planning:'))
        elif link[0] == 'peerreview':
            facts.add_term (pulse.utils.gettext ('Peer Review:'))
        elif link[0] == 'techreview':
            facts.add_term (pulse.utils.gettext ('Technical Review:'))
        elif link[0] == 'finalreview':
            facts.add_term (pulse.utils.gettext ('Final Review:'))
        elif link[0] == 'review':
            facts.add_term (pulse.utils.gettext ('Review:'))
        else:
            facts.add_term (pulse.utils.gettext ('Link:'))
        facts.add_entry (pulse.html.Link (link[1], link[2]))
    box.add_content (facts)

    # Developers
    box = pulse.html.SidebarBox (pulse.utils.gettext ('Developers'))
    page.add_sidebar_content (box)
    rels = pulse.db.DocumentEntity.get_related (subj=doc)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
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

    page.add_tab ('activity', pulse.utils.gettext ('Activity'))
    page.add_tab ('files', pulse.utils.gettext ('Files'))
    page.add_tab ('translations', pulse.utils.gettext ('Translations'))


def output_ajax_figures (response, doc, **kw):
    figures = doc.data.get('figures', {})
    response.set_contents (get_figures (doc, figures))


def output_ajax_graphmap (response, doc, **kw):
    query = kw.get ('query', {})
    id = query.get('id')
    num = query.get('num')
    filename = query.get('filename')
    
    of = pulse.db.OutputFile.select (type=u'graphs', ident=doc.ident, filename=filename)
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, doc.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'),
                                                 count=int(id), num=int(num), map_only=True)
        response.set_contents (graph)
    except IndexError:
        pass


def output_ajax_xmlfiles (response, doc, **kw):
    xmlfiles = doc.data.get('xmlfiles', [])
    response.set_contents (get_xmlfiles (doc, xmlfiles))


def output_ajax_tab (response, doc, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'info':
        response.set_contents (get_info_tab (doc, **kw))
    elif tab == 'activity':
        response.set_contents (get_activity_tab (doc, **kw))
    elif tab == 'files':
        response.set_contents (get_files_tab (doc, **kw))
    elif tab == 'translations':
        response.set_contents (get_translations_tab (doc, **kw))


def output_ajax_commits (response, doc, **kw):
    query = kw.get('query', {})
    weeknum = query.get('weeknum', None)
    files = (doc.data.get ('xmlfiles', [])
             + doc.data.get ('files', [])
             + doc.data.get ('figures', []))
    files = [os.path.join (doc.scm_dir, f) for f in files]
    if weeknum != None:
        weeknum = int(weeknum)
        thisweek = pulse.utils.weeknum ()
        ago = thisweek - weeknum
        cnt = pulse.db.Revision.count_revisions (branch=doc.parent, files=files, weeknum=weeknum)
        revs = pulse.db.Revision.select_revisions (branch=doc.parent, files=files, weeknum=weeknum)
        revs = list(revs[:20])
    else:
        cnt = pulse.db.Revision.count_revisions (branch=doc.parent, files=files)
        revs = pulse.db.Revision.select_revisions (branch=doc.parent, files=files,
                                                   week_range=(pulse.utils.weeknum()-52,))
        revs = list(revs[:10])
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
    response.set_contents (get_commits_div (doc, revs, title))


def get_info_tab (doc, **kw):
    facts = pulse.html.FactsTable()

    if doc.error != None:
        facts.add_fact (pulse.utils.gettext ('Error'),
                        pulse.html.AdmonBox (pulse.html.AdmonBox.error, doc.error))
        facts.add_fact_divider ()

    sep = False
    try:
        desc = doc.localized_desc
        facts.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    rels = pulse.db.SetModule.get_related (pred=doc.parent)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(rset.pulse_url + '#documents', rset.title)
                                  for rset in sets])
        span.set_divider (pulse.html.BULLET)
        facts.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    facts.add_fact (pulse.utils.gettext ('Module'), pulse.html.Link (doc.parent))

    rels = pulse.db.Documentation.get_related (pred=doc)
    if len(rels) > 0:
        objs = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(obj) for obj in objs])
        span.set_divider (pulse.html.BULLET)
        facts.add_fact (pulse.utils.gettext ('Describes'), span)
        sep = True

    if sep:
        facts.add_fact_divider ()
    
    checkout = pulse.scm.Checkout.from_record (doc, checkout=False, update=False)
    facts.add_fact (pulse.utils.gettext ('Location'),
                   checkout.get_location (doc.scm_dir, doc.scm_file))

    if doc.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (doc.mod_datetime.strftime('%Y-%m-%d %T'))
        if doc.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (doc.mod_person))
        facts.add_fact (pulse.utils.gettext ('Last Modified'), span)

    facts.add_fact_divider ()
    facts.add_fact (pulse.utils.gettext ('Score'), str(doc.mod_score))

    if doc.updated is not None:
        facts.add_fact_divider ()
        facts.add_fact (pulse.utils.gettext ('Last Updated'),
                        doc.updated.strftime('%Y-%m-%d %T'))
    return facts


def get_activity_tab (doc, **kw):
    box = pulse.html.Div ()
    of = pulse.db.OutputFile.select (type=u'graphs', ident=doc.ident, filename=u'commits-0.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, doc.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'))
        box.add_content (graph)
    except IndexError:
        pass

    files = (doc.data.get ('xmlfiles', [])
             + doc.data.get ('files', [])
             + doc.data.get ('figures', []))
    files = [os.path.join (doc.scm_dir, f) for f in files]
    cnt = pulse.db.Revision.count_revisions (branch=doc.parent, files=files)
    revs = pulse.db.Revision.select_revisions (branch=doc.parent, files=files,
                                               week_range=(pulse.utils.weeknum()-52,))
    revs = list(revs[:10])
    title = (pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    div = get_commits_div (doc, revs, title)
    box.add_content (div)

    return box


def get_files_tab (doc, **kw):
    columns = pulse.html.ColumnBox (2)

    # Files
    box = pulse.html.InfoBox (pulse.utils.gettext ('Files'))
    columns.add_to_column (0, box)
    xmlfiles = doc.data.get('xmlfiles', []) + doc.data.get ('files', [])
    if len(xmlfiles) > 20:
        div = pulse.html.AjaxBox (doc.pulse_url + '?ajax=xmlfiles')
    else:
        div = get_xmlfiles (doc, xmlfiles)
    box.add_content (div)

    # Figures
    figures = doc.data.get('figures', {})
    if len(figures) > 0:
        box = pulse.html.InfoBox (pulse.utils.gettext ('Figures'))
        columns.add_to_column (1, box)
        if len(figures) > 20:
            div = pulse.html.AjaxBox (doc.pulse_url + '?ajax=figures')
        else:
            div = get_figures (doc, figures)
        box.add_content (div)

    return columns


def get_translations_tab (doc, **kw):
    cont = pulse.html.ContainerBox ()
    cont.set_id ('c-translations')
    pad = pulse.html.PaddingBox ()
    cont.add_content (pad)

    of = pulse.db.OutputFile.select (type=u'l10n', ident=doc.ident,
                                     filename=(doc.ident.split('/')[-2] + u'.pot'))
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

    translations = pulse.db.Branch.select_with_statistic ([u'Messages', u'ImageMessages'],
                                                          type=u'Translation', parent=doc)
    # FIXME STORM
    translations = pulse.utils.attrsorted (list(translations), (0, 'title'))
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
        for translation, mstat, istat in translations:
            span = pulse.html.Span (os.path.basename (translation.scm_dir))
            span.add_class ('title')
            link = pulse.html.Link (translation.pulse_url, span)
            row = [link]
            percent = 0
            stat1 = mstat.stat1
            stat2 = mstat.stat2
            total = mstat.total
            untranslated = total - stat1 - stat2
            try:
                percent = math.floor (100 * (float(stat1) / total))
            except:
                percent = 0
            span = pulse.html.Span ('%i%%' % percent)
            span.add_class ('percent')
            row.append (span)

            row.append (pulse.utils.gettext ('%i.%i.%i') %
                        (stat1, stat2, untranslated))
            istat1 = istat.stat1
            itotal = istat.total
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
    return cont


def get_xmlfiles (doc, xmlfiles):
    cont = pulse.html.ContainerBox()
    cont.set_id ('c-xmlfiles')
    dl = pulse.html.DefinitionList()
    cont.add_content (dl)
    if len(xmlfiles) > 1:
        cont.set_sortable_tag ('dt')
        cont.set_sortable_class ('xmlfiles')
        cont.add_sort_link ('title', pulse.utils.gettext ('name'), 1)
        cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    files = [os.path.join (doc.scm_dir, xmlfile) for xmlfile in xmlfiles]
    commits = pulse.db.RevisionFileCache.select_with_revision (branch=doc.parent, files=files)
    revisions = {}
    for cache, revision in list(commits):
        revisions[cache.filename] = revision
    for xmlfile in xmlfiles:
        span = pulse.html.Span (xmlfile)
        span.add_class ('title')
        dl.add_term (span, classname='xmlfiles')
        fullfile = os.path.join (doc.scm_dir, xmlfile)
        commit = revisions.get (fullfile)
        if commit != None:
            span = pulse.html.Span (divider=pulse.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            mspan = pulse.html.Span()
            mspan.add_content (commit.datetime.strftime('%Y-%m-%d %T'))
            mspan.add_class ('mtime')
            span.add_content (mspan)
            span.add_content (' by ')
            span.add_content (pulse.html.Link (commit.person))
            dl.add_entry (span)
    return cont


def get_figures (doc, figures):
    cont = pulse.html.ContainerBox()
    cont.set_id ('c-figures')
    cont.set_sortable_tag ('dt')
    cont.set_sortable_class ('figures')
    cont.add_sort_link ('title', pulse.utils.gettext ('name'), 1)
    cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    ofs = pulse.db.OutputFile.select (type=u'figures', ident=doc.ident, subdir=u'C')
    ofs_by_source = {}
    files = []
    for of in ofs:
        ofs_by_source[of.source] = of
        files.append (os.path.join (doc.scm_dir, of.source))
    dl = pulse.html.DefinitionList ()
    cont.add_content (dl)
    commits = pulse.db.RevisionFileCache.select_with_revision (branch=doc.parent, files=files)
    revisions = {}
    for cache, revision in list(commits):
        revisions[cache.filename] = revision
    for figure in sorted(figures.keys()):
        of = ofs_by_source.get(figure)
        if of:
            span = pulse.html.Span (pulse.html.Link (of.pulse_url, figure, classname='zoom'))
            span.add_class ('title')
            dl.add_term (span, classname='figures')
            fullfile = os.path.join (doc.scm_dir, of.source)
            commit = revisions.get (fullfile)
            if commit != None:
                span = pulse.html.Span(divider=pulse.html.SPACE)
                # FIXME: i18n, word order, but we want to link person
                mspan = pulse.html.Span()
                mspan.add_content (commit.datetime.strftime('%Y-%m-%d %T'))
                mspan.add_class ('mtime')
                span.add_content (mspan)
                span.add_content (' by ')
                span.add_content (pulse.html.Link (commit.person))
                dl.add_entry (span)
            if figures[figure].get('comment', '') != '':
                dl.add_entry (pulse.html.EllipsizedLabel (figures[figure]['comment'], 80),
                              classname='desc')
        else:
            dl.add_term (figure)
    return cont


def get_commits_div (doc, revs, title):
    div = pulse.html.Div (widget_id='commits')
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
        span.add_content (pulse.html.Link (rev.person))
        dl.add_term (span)
        dl.add_entry (pulse.html.PopupLink.from_revision (rev, branch=doc.parent))
    return div
