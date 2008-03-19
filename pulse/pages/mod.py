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

import pulse.config
import pulse.graphs
import pulse.models as db
import pulse.html
import pulse.scm
import pulse.utils

people_cache = {}

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 3:
        branchables = db.Branchable.objects.filter(ident=('/' + '/'.join(path)))
        try:
            branchable = branchables[0]
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

        branch = branchable.default
        if branch == None:
            kw = {'http': http}
            kw['title'] = pulse.utils.gettext ('Default Branch Not Found')
            # FIXME: this is not a good place to redirect
            kw['pages'] = [('mod', pulse.utils.gettext ('All Modules'))]
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch for the module %s')
                % path[2],
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
        return output_ajax_commits (branch, path=path, query=query, http=http, fd=fd)
    elif query.get('ajax', None) == 'revfiles':
        return output_ajax_revfiles (branch, path=path, query=query, http=http, fd=fd)
    else:
        return output_module (branch, path=path, query=query, http=http, fd=fd)


def output_module (module, **kw):
    branchable = module.branchable
    checkout = pulse.scm.Checkout.from_record (module, checkout=False, update=False)

    page = pulse.html.RecordPage (module, http=kw.get('http', True))

    branches = pulse.utils.attrsorted (list(branchable.branches.all()), 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != module.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    if module.data.has_key ('screenshot'):
        page.add_screenshot (module.data['screenshot'])

    sep = False
    try:
        page.add_fact (pulse.utils.gettext ('Description'),
                       module.localized_desc)
        sep = True
    except:
        pass

    rels = db.SetModule.get_related (pred=module)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(set) for set in sets])
        span.set_divider (pulse.html.BULLET)
        page.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    if sep:
        page.add_fact_sep ()

    page.add_fact (pulse.utils.gettext ('Location'), checkout.location)

    if module.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (module.mod_datetime.strftime('%Y-%m-%d %T'))
        if module.mod_person != None:
            span.add_content (' by ')
            people_cache[module.mod_person.id] = module.mod_person
            span.add_content (pulse.html.Link (module.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    if module.data.has_key ('tarname'):
        page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Tarball Name'), module.data['tarname'])
    if module.data.has_key ('tarversion'):
        if not module.data.has_key ('tarname'):
            page.add_fact_sep ()
        page.add_fact (pulse.utils.gettext ('Version'), module.data['tarversion'])

    page.add_fact_sep ()
    page.add_fact (pulse.utils.gettext ('Score'), str(module.mod_score))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    # Developers
    box = get_developers_box (module)
    columns.add_to_column (0, box)

    # Activity
    box = pulse.html.InfoBox ('activity', pulse.utils.gettext ('Activity'))
    columns.add_to_column (0, box)
    of = db.OutputFile.objects.filter (type='graphs', ident=module.ident, filename='commits.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, module.pulse_url)
        box.add_content (graph)
    except IndexError:
        pass

    revs = db.Revision.select_revisions (branch=module)
    cnt = revs.count()
    revs = revs[:10]
    div = get_commits_div (module, revs,
                           pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    box.add_content (div)

    # Dependencies
    box = pulse.html.InfoBox ('dependencies', pulse.utils.gettext ('Dependencies'))
    columns.add_to_column (0, box)
    deps = db.ModuleDependency.get_related (subj=module)
    deps = pulse.utils.attrsorted (list(deps), ['pred', 'scm_module'])
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

    # Programs and Libraries
    for branchtype, boxid, title in (
        ('Application', 'applications', pulse.utils.gettext ('Applications')),
        ('Capplet', 'capplets', pulse.utils.gettext ('Capplets')),
        ('Applet', 'applets', pulse.utils.gettext ('Applets')),
        ('Library', 'libraries', pulse.utils.gettext ('Libraries')) ):

        box = get_info_box (module, branchtype, boxid, title)
        if box != None:
            columns.add_to_column (1, box)

    # Documents
    box = pulse.html.InfoBox ('documents', pulse.utils.gettext ('Documents'))
    columns.add_to_column (1, box)
    docs = module.select_children ('Document')
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
    domains = module.select_children ('Domain')
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
                div = pulse.html.Div()
                pad.add_content (div)

                linkdiv = pulse.html.Div()
                linkspan = pulse.html.Span (divider=pulse.html.SPACE)
                linkdiv.add_content (linkspan)
                div.add_content (linkdiv)
                linkspan.add_content (pulse.html.Link (of.pulse_url,
                                                       pulse.utils.gettext ('POT file'),
                                                       icon='download' ))
                # FIXME: i18n reordering
                linkspan.add_content (pulse.utils.gettext ('(%i messages)')
                                      % of.statistic)
                linkspan.add_content (pulse.utils.gettext ('on %s')
                                      % of.datetime.strftime('%Y-%m-%d %T'))
                missing = of.data.get ('missing', [])
                if len(missing) > 0:
                    msg = pulse.utils.gettext('%i missing files') % len(missing)
                    admon = pulse.html.AdmonBox (pulse.html.AdmonBox.warning, msg, tag='span')
                    mdiv = pulse.html.Div()
                    popup = pulse.html.PopupLink (admon, '\n'.join(missing))
                    mdiv.add_content (popup)
                    div.add_content (mdiv)
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

    page.output(fd=kw.get('fd', None))

    return 0


def output_ajax_commits (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment ()
    weeknum = int(query.get('weeknum', 0))
    thisweek = pulse.utils.weeknum (datetime.datetime.now())
    ago = thisweek - weeknum
    revs = db.Revision.select_revisions (branch=module, weeknum=weeknum)
    cnt = revs.count()
    revs = revs[:20]
    if ago == 0:
        title = (pulse.utils.gettext('Showing %i of %i commits from this week:')
                 % (len(revs), cnt))
    elif ago == 1:
        title = (pulse.utils.gettext('Showing %i of %i commits from last week:')
                 % (len(revs), cnt))
    else:
        title = (pulse.utils.gettext('Showing %i of %i commits from %i weeks ago:')
                 % (len(revs), cnt, ago))
    div = get_commits_div (module, revs, title)
    page.add_content (div)
    page.output(fd=kw.get('fd', None))
    return 0


def output_ajax_revfiles (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment ()

    if module.scm_server.endswith ('/svn/'):
        base = module.scm_server[:-4] + 'viewvc/'
        colon = base.find (':')
        if colon < 0:
            page.output(fd=kw.get('fd', None))
            return 404
        if base[:colon] != 'http':
            base = 'http' + base[colon:]
        if module.scm_path != None:
            base += module.scm_path
        elif module.scm_branch == 'trunk':
            base += module.scm_module + '/trunk/'
        else:
            base += module.scm_module + '/branches/' + module.scm_branch + '/'

    revid = query.get('revid', None)
    revision = db.Revision.objects.get(id=int(revid))
    files = db.RevisionFile.objects.filter (revision=revision)

    mlink = pulse.html.MenuLink (revision.revision, menu_only=True)
    page.add_content (mlink)
    for file in files:
        url = base + file.filename
        url += '?r1=%s&r2=%s' % (file.prevrev, file.filerev)
        mlink.add_link (url, file.filename)

    page.output(fd=kw.get('fd', None))
    return 0


def get_developers_box (module):
    box = pulse.html.InfoBox ('developers', pulse.utils.gettext ('Developers'))
    rels = db.ModuleEntity.get_related (subj=module)
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
    return box


def get_info_box (module, branchtype, boxid, title):
    objs = module.select_children (branchtype)
    objs = pulse.utils.attrsorted (list(objs), 'title')
    if len(objs) > 0:
        box = pulse.html.InfoBox (boxid, title)
        for obj in objs:
            lbox = box.add_link_box (obj)
            doc = db.Documentation.get_related (subj=obj)
            try:
                doc = doc[0]
                lbox.add_fact (pulse.utils.gettext ('Documentaion'), doc.pred)
            except IndexError:
                pass
        return box
    return None


def get_commits_div (module, revs, title):
    div = pulse.html.Div (id='commits')
    div.add_content (title)
    dl = pulse.html.DefinitionList()
    div.add_content (dl)
    curweek = None
    for rev in revs:
        if curweek != None and curweek != rev.weeknum:
            dl.add_divider ()
        curweek = rev.weeknum
        # FIXME: i18n word order
        span = pulse.html.Span (divider=pulse.html.SPACE)
        span.add_content (rev.display_revision (module))
        span.add_content ('on')
        span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
        span.add_content ('by')
        if not rev.person_id in people_cache:
            people_cache[rev.person_id] = rev.person
        person = people_cache[rev.person_id]
        span.add_content (pulse.html.Link (person))
        dl.add_term (span)
        dl.add_entry (pulse.html.PopupLink.from_revision (rev, branch=module))
    return div
