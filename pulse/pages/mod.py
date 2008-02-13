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
import math
import os

import pulse.config
import pulse.graphs
import pulse.models as db
import pulse.html
import pulse.scm
import pulse.utils

people_cache = {}

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 3:
        modules = db.Branchable.objects.filter(ident=('/' + '/'.join(path)))
        try:
            module = modules[0]
        except IndexError:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Module Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the module %s') % path[2],
                **kw)
            page.output(fd=fd)
            return 404

        branch = module.branch
        if branch == None:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Default Branch Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch for the module %s') % path[2],
                **kw)
            page.output(fd=fd)
            return 404
    elif len(path) == 4:
        branches = db.Branch.objects.filter (ident=('/' + '/'.join(path)))
        try:
            branch = branches[0]
        except IndexError:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Branch Not Found')
            modules = db.Branchable.objects.filter (ident=('/' + '/'.join(path[:-1])))
            if modules.count() > 0:
                module = modules[0]
                # FIXME: i18n
                kw['pages'] = [(module.ident, module.title)]
            else:
                kw['pages'] = []
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the module %s') % (path[3], path[2]),
                **kw)
            page.output(fd=fd)
            return 404
    else:
        # FIXME: redirect to /set or something
        pass

    if query.get('ajax', None) == 'commits':
        return output_ajax_commits (branch, path, query, http, fd)
    else:
        return output_branch (branch, path, query, http, fd)


def output_branch (branch, path=[], query={}, http=True, fd=None):
    module = branch.branchable
    checkout = pulse.scm.Checkout.from_record (branch, checkout=False, update=False)

    page = pulse.html.RecordPage (branch, http=http)

    branches = pulse.utils.attrsorted (list(module.branches.all()), 'scm_branch')
    if len(branches) > 1:
        for b in branches:
            if b.ident != branch.ident:
                page.add_sublink (b.pulse_url, b.ident.split('/')[-1])
            else:
                page.add_sublink (None, b.ident.split('/')[-1])

    if branch.data.has_key ('screenshot'):
        page.add_screenshot (branch.data['screenshot'])

    sep = False
    try:
        desc = branch.localized_desc
        page.add_fact (pulse.utils.gettext ('Description'), desc)
        sep = True
    except:
        pass

    rels = db.SetModule.get_related (pred=branch)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(rel.subj) for rel in rels])
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    if sep: page.add_fact_sep ()

    page.add_fact (pulse.utils.gettext ('Location'), checkout.location)

    if branch.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (branch.mod_datetime.strftime('%Y-%m-%d %T'))
        if branch.mod_person != None:
            span.add_content (' by ')
            people_cache[branch.mod_person.id] = branch.mod_person
            span.add_content (pulse.html.Link (branch.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    if branch.data.has_key ('tarname'):
        page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Tarball Name'), branch.data['tarname'])
    if branch.data.has_key ('tarversion'):
        if not branch.data.has_key ('tarname'):
            page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Version'), branch.data['tarversion'])

    page.add_fact_sep ()
    page.add_fact (pulse.utils.gettext ('Score'), str(branch.mod_score))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    developers = db.ModuleEntity.get_related (subj=branch)
    developers = pulse.utils.attrsorted (list(developers), ['pred', 'title'])
    if len(developers) > 0:
        for rel in developers:
            lbox = box.add_link_box (rel.pred)
            if rel.maintainer:
                lbox.add_badge ('maintainer')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))
    columns.add_to_column (0, box)

    # Activity
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    columns.add_to_column (0, box)
    of = db.OutputFile.objects.filter (type='graphs', ident=branch.ident, filename='commits.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, branch.pulse_url)
        box.add_content (graph)
    except IndexError:
        pass

    revs = db.Revision.select_revisions (branch=branch)
    cnt = revs.count()
    revs = revs[:10]
    div = get_commits_div (branch, revs,
                           pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    box.add_content (div)

    # Dependencies
    box = pulse.html.InfoBox ('dependencies', pulse.utils.gettext ('Dependencies'))
    columns.add_to_column (0, box)
    deps = db.ModuleDependency.get_related (subj=branch)
    deps = pulse.utils.attrsorted (list(deps), 'pred', 'scm_module')
    d1 = pulse.html.Div()
    d2 = pulse.html.Div()
    box.add_content (d1)
    box.add_content (pulse.html.Rule())
    box.add_content (d2)
    for dep in deps:
        div = pulse.html.Div ()
        link = pulse.html.Link (dep.pred.pulse_url, dep.pred.scm_module)
        div.add_content (link)
        if dep.direct:
            d1.add_content (div)
        else:
            d2.add_content (div)

    # Applications
    apps = branch.select_children ('Application')
    apps = pulse.utils.attrsorted (list(apps), 'title')
    if len(apps) > 0:
        box = pulse.html.InfoBox ('applications', pulse.utils.gettext ('Applications'))
        columns.add_to_column (1, box)
        for app in apps:
            lbox = box.add_link_box (app)
            doc = db.Documentation.get_related (subj=app)
            try:
                doc = doc[0]
                lbox.add_fact (pulse.utils.gettext ('Documentaion'), doc.pred)
            except IndexError:
                pass

    # Capplets
    capps = branch.select_children ('Capplet')
    capps = pulse.utils.attrsorted (list(capps), 'title')
    if len(capps) > 0:
        box = pulse.html.InfoBox ('capplets', pulse.utils.gettext ('Capplets'))
        columns.add_to_column (1, box)
        for capp in capps:
            lbox = box.add_link_box (capp)
            doc = db.Documentation.get_related (subj=capp)
            try:
                doc = doc[0]
                lbox.add_fact (pulse.utils.gettext ('Documentaion'), doc.pred)
            except IndexError:
                pass

    # Applets
    applets = branch.select_children ('Applet')
    applets = pulse.utils.attrsorted (list(applets), 'title')
    if len(applets) > 0:
        box = pulse.html.InfoBox ('applets', pulse.utils.gettext ('Applets'))
        columns.add_to_column (1, box)
        for applet in applets:
            box.add_link_box (applet)

    # Libraries
    libs = branch.select_children ('Library')
    libs = pulse.utils.attrsorted (list(libs), 'title')
    if len(libs) > 0:
        box = pulse.html.InfoBox ('libraries', pulse.utils.gettext ('Libraries'))
        columns.add_to_column (1, box)
        for lib in libs:
            box.add_link_box (lib)

    # Documents
    box = pulse.html.InfoBox ('documents', pulse.utils.gettext ('Documents'))
    columns.add_to_column (1, box)
    docs = branch.select_children ('Document')
    docs = pulse.utils.attrsorted (list(docs), 'title')
    if len(docs) > 0:
        for doc in docs:
            lbox = box.add_link_box (doc)
            res = doc.select_children ('Translation')
            lbox.add_fact (None, pulse.utils.gettext ('%i translations') % res.count())
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documents') ))

    # Translations
    box = pulse.html.InfoBox ('translations', pulse.utils.gettext ('Translations'))
    columns.add_to_column (1, box)
    domains = branch.select_children ('Domain')
    domains = pulse.utils.attrsorted (list(domains), 'title')
    if len(domains) > 0:
        for domain in domains:
            domainid = domain.ident.split('/')[-2].replace('-', '_')
            translations = db.Branch.select_with_statistic ('Messages',
                                                            type='Translation', parent=domain)
            translations = pulse.utils.attrsorted (list(translations), 'title')
            cont = pulse.html.ContainerBox ()
            cont.set_id ('po_' + domainid)
            cont.set_title (pulse.utils.gettext ('%s (%s)')
                            % (domain.title, len(translations)))
            box.add_content (cont)
            pad = pulse.html.PaddingBox ()
            cont.add_content (pad)

            if domain.scm_dir == 'po':
                potfile = domain.scm_module + '.pot'
            else:
                potfile = domain.scm_dir + '.pot'
            of = db.OutputFile.objects.filter (type='l10n', ident=domain.ident, filename=potfile)
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

            if len(translations) == 0:
                pad.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                                       pulse.utils.gettext ('No translations') ))
            else:
                cont.set_sortable_tag ('tr')
                cont.set_sortable_class ('po_' + domainid)
                cont.add_sort_link ('title', pulse.utils.gettext ('lang'), False)
                cont.add_sort_link ('percent', pulse.utils.gettext ('percent'))
                grid = pulse.html.GridBox ()
                pad.add_content (grid)
                for translation in translations:
                    span = pulse.html.Span (translation.scm_file[:-3])
                    span.add_class ('title')
                    row = [span]
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
                    idx = grid.add_row (*row)
                    grid.add_row_class (idx, 'po')
                    grid.add_row_class (idx, 'po_' + domainid)
                    if percent >= 80:
                        grid.add_row_class (idx, 'po80')
                    elif percent >= 50:
                        grid.add_row_class (idx, 'po50')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No domains') ))

    page.output(fd=fd)

    return 0


def output_ajax_commits (branch, path=[], query={}, http=True, fd=None):
    page = pulse.html.Fragment ()
    weeknum = int(query.get('weeknum', 0))
    thisweek = pulse.utils.weeknum (datetime.datetime.now())
    ago = thisweek - weeknum
    revs = db.Revision.select_revisions (branch=branch, weeknum=weeknum)
    cnt = revs.count()
    revs = revs[:20]
    if ago == 0:
        title = pulse.utils.gettext('Showing %i of %i commits from this week:') % (len(revs), cnt)
    elif ago == 1:
        title = pulse.utils.gettext('Showing %i of %i commits from last week:') % (len(revs), cnt)
    else:
        title = pulse.utils.gettext('Showing %i of %i commits from %i weeks ago:') % (len(revs), cnt, ago)
    div = get_commits_div (branch, revs, title)
    page.add_content (div)
    page.output(fd=fd)
    return 0


def get_commits_div (branch, revs, title):
    div = pulse.html.Div (id='commits')
    div.add_content (title)
    dl = pulse.html.DefinitionList()
    div.add_content (dl)
    for rev in revs:
        # FIXME: i18n word order
        span = pulse.html.Span (divider=pulse.html.SPACE)
        span.add_content (rev.revision)
        span.add_content ('on')
        span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
        span.add_content ('by')
        if not rev.person_id in people_cache:
            people_cache[rev.person_id] = rev.person
        person = people_cache[rev.person_id]
        span.add_content (pulse.html.Link (person))
        dl.add_term (span)
        dl.add_entry (pulse.html.PopupLink.from_revision (branch, rev))
    return div
