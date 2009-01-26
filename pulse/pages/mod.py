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
import urllib

import pulse.config
import pulse.graphs
import pulse.models as db
import pulse.html
import pulse.scm
import pulse.utils

def main (path, query, http=True, fd=None):
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

        branch = branchable.get_default ()
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
                pulse.utils.gettext ('Pulse could not find the branch %s of the module %s')
                % (path[3], path[2]),
                **kw)
            page.output(fd=fd)
            return 404
    else:
        # FIXME: redirect to /set or something
        pass

    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    if query.get('ajax', None) == 'tab':
        return output_ajax_tab (branch, **kw)
    elif query.get('ajax', None) == 'commits':
        return output_ajax_commits (branch, **kw)
    elif query.get('ajax', None) == 'domain':
        return output_ajax_domain (branch, **kw)
    elif query.get('ajax', None) == 'graphmap':
        return output_ajax_graphmap (branch, **kw)
    elif query.get('ajax', None) == 'revfiles':
        return output_ajax_revfiles (branch, **kw)
    else:
        return output_module (branch, **kw)

synopsis_sort = -1
def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.SectionBox (pulse.utils.gettext ('Modules'))
    txt = (pulse.utils.gettext ('Pulse is watching %i branches in %i modules.') %
           (db.Branch.objects.filter(type='Module').count(),
            db.Branchable.objects.filter(type='Module').count() ))
    box.add_content (pulse.html.Div (txt))

    columns = pulse.html.ColumnBox (2)
    box.add_content (columns)

    modules = db.Branch.objects.filter (type='Module').order_by ('-mod_score')
    bl = pulse.html.BulletList ()
    bl.set_title (pulse.utils.gettext ('Kicking ass and taking names:'))
    columns.add_to_column (0, bl)
    modules = modules[:6]
    scm_mods = {}
    for module in modules:
        scm_mods.setdefault (module.scm_module, 0)
        scm_mods[module.scm_module] += 1
    for module in modules:
        if scm_mods[module.scm_module] > 1:
            bl.add_link (module.get_pulse_url(), module.get_branch_title())
        else:
            bl.add_link (module)

    modules = db.Branch.objects.filter (type='Module').order_by ('-mod_score_diff')
    bl = pulse.html.BulletList ()
    bl.set_title (pulse.utils.gettext ('Recently rocking:'))
    columns.add_to_column (1, bl)
    modules = modules[:6]
    scm_mods = {}
    for module in modules:
        scm_mods.setdefault (module.scm_module, 0)
        scm_mods[module.scm_module] += 1
    for module in modules:
        if scm_mods[module.scm_module] > 1:
            bl.add_link (module.get_pulse_url(), module.get_branch_title())
        else:
            bl.add_link (module)
    return box


def output_module (module, **kw):
    branchable = module.branchable

    page = pulse.html.Page (module, http=kw.get('http', True))

    branches = pulse.utils.attrsorted (list(branchable.branches.all()),
                                       '-is_default', 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != module.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    if module.data.has_key ('screenshot'):
        page.add_screenshot (module.data['screenshot'])

    page.add_tab ('info', 'Info')
    box = get_info_tab (module, **kw)
    page.add_to_tab ('info', box)

    # Developers
    box = get_developers_box (module)
    page.add_sidebar_content (box)

    page.add_tab ('activity', pulse.utils.gettext ('Activity'))
    page.add_tab ('components', pulse.utils.gettext ('Components'))
    if module.select_children ('Domain').count() > 0:
        page.add_tab ('translations', pulse.utils.gettext ('Translations'))

    # Dependencies
    deps = db.ModuleDependency.get_related (subj=module)
    deps = pulse.utils.attrsorted (list(deps), ['pred', 'scm_module'])
    if len(deps) > 0:
        box = pulse.html.SidebarBox (pulse.utils.gettext ('Dependencies'))
        page.add_sidebar_content (box)
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


    page.output(fd=kw.get('fd'))

    return 0


def output_ajax_tab (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    tab = query.get('tab', None)
    if tab == 'info':
        page.add_content (get_info_tab (module, **kw))
    elif tab == 'activity':
        page.add_content (get_activity_tab (module, **kw))
    elif tab == 'components':
        page.add_content (get_components_tab (module, **kw))
    elif tab == 'translations':
        page.add_content (get_translations_tab (module, **kw))
    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_domain (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    ident = query.get('domain', None)

    domain = db.Branch.objects.get (ident=ident)
    domainid = domain.ident.split('/')[-2].replace('-', '_')
    translations = db.Branch.select_with_statistic ('Messages',
                                                    type='Translation', parent=domain)
    translations = pulse.utils.attrsorted (list(translations), 'title')
    pagediv = pulse.html.Div ()
    pad = pulse.html.PaddingBox ()
    pagediv.add_content (pad)
    page.add_content (pagediv)

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
            percent = total and math.floor (100 * (float(stat1) / total)) or 0
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

    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_graphmap (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    id = query.get('id')
    num = query.get('num')
    filename = query.get('filename')
    
    of = db.OutputFile.objects.filter (type='graphs', ident=module.ident, filename=filename)
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, module.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'),
                                                 count=int(id), num=int(num), map_only=True)
        page.add_content (graph)
    except IndexError:
        pass
    
    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_commits (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    weeknum = query.get('weeknum', None)
    if weeknum != None:
        weeknum = int(weeknum)
        thisweek = pulse.utils.weeknum (datetime.datetime.now())
        ago = thisweek - weeknum
        revs = db.Revision.select_revisions (branch=module, weeknum=weeknum)
        cnt = revs.count()
        revs = revs[:20]
    else:
        revs = db.Revision.select_revisions (branch=module)
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
    div = get_commits_div (module, revs, title)
    page.add_content (div)
    page.output(fd=kw.get('fd'))
    return 0


def output_ajax_revfiles (module, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))

    if module.scm_server.endswith ('/svn/'):
        base = module.scm_server[:-4] + 'viewvc/'
        colon = base.find (':')
        if colon < 0:
            page.output(fd=kw.get('fd'))
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

    page.output(fd=kw.get('fd'))
    return 0


def get_info_tab (module, **kw):
    div = pulse.html.PaddingBox()

    if module.error != None:
        div.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.error, module.error))

    facts = pulse.html.FactsTable()
    div.add_content (facts)

    sep = False
    try:
        facts.add_fact (pulse.utils.gettext ('Description'),
                       module.localized_desc)
        sep = True
    except:
        pass

    rels = db.SetModule.get_related (pred=module)
    if len(rels) > 0:
        sets = pulse.utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = pulse.html.Span (*[pulse.html.Link(rset) for rset in sets])
        span.set_divider (pulse.html.BULLET)
        facts.add_fact (pulse.utils.gettext ('Release Sets'), span)
        sep = True

    if sep:
        facts.add_fact_divider ()

    checkout = pulse.scm.Checkout.from_record (module, checkout=False, update=False)
    facts.add_fact (pulse.utils.gettext ('Location'), checkout.location)

    if module.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (module.mod_datetime.strftime('%Y-%m-%d %T'))
        if module.mod_person != None:
            span.add_content (' by ')
            person = db.Entity.set_cached (module.mod_person.id, module.mod_person)
            span.add_content (pulse.html.Link (person))
        facts.add_fact (pulse.utils.gettext ('Last Modified'), span)

    if module.data.has_key ('tarname'):
        facts.add_fact_divider ()
        facts.add_fact (pulse.utils.gettext ('Tarball Name'), module.data['tarname'])
    if module.data.has_key ('tarversion'):
        if not module.data.has_key ('tarname'):
            facts.add_fact_divider ()
        facts.add_fact (pulse.utils.gettext ('Version'), module.data['tarversion'])

    facts.add_fact_divider ()
    facts.add_fact (pulse.utils.gettext ('Score'), str(module.mod_score))

    return div


def get_activity_tab (module, **kw):
    box = pulse.html.Div ()
    of = db.OutputFile.objects.filter (type='graphs', ident=module.ident, filename='commits-0.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, module.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'))
        box.add_content (graph)
    except IndexError:
        pass

    revs = db.Revision.select_revisions (branch=module)
    cnt = revs.count()
    revs = revs[:10]
    title = (pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    div = get_commits_div (module, revs, title)
    box.add_content (div)

    return box


def get_components_tab (module, **kw):
    columns = pulse.html.ColumnBox (2)

    # Programs and Libraries
    for branchtype, title in (
        ('Application', pulse.utils.gettext ('Applications')),
        ('Capplet', pulse.utils.gettext ('Capplets')),
        ('Applet', pulse.utils.gettext ('Applets')),
        ('Library', pulse.utils.gettext ('Libraries')) ):

        box = get_component_info_box (module, branchtype, title)
        if box != None:
            columns.add_to_column (0, box)

    # Documents
    box = pulse.html.InfoBox (pulse.utils.gettext ('Documents'))
    columns.add_to_column (1, box)
    docs = module.select_children ('Document')
    docs = pulse.utils.attrsorted (list(docs), 'title')
    if len(docs) > 0:
        if len(docs) > 1:
            box.add_sort_link ('title', pulse.utils.gettext ('title'), 1)
            box.add_sort_link ('status', pulse.utils.gettext ('status'), 0)
            box.add_sort_link ('translations', pulse.utils.gettext ('translations'), 0)
        for doc in docs:
            lbox = box.add_link_box (doc)
            lbox.add_fact (pulse.utils.gettext ('status'),
                           pulse.html.StatusSpan (doc.data.get('status')))
            res = doc.select_children ('Translation')
            span = pulse.html.Span (str(res.count()))
            span.add_class ('translations')
            lbox.add_fact (pulse.utils.gettext ('translations'), span)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documents') ))

    return columns


def get_translations_tab (module, **kw):
    box = pulse.html.PaddingBox ()
    domains = module.select_children ('Domain')
    domains = pulse.utils.attrsorted (list(domains), 'title')
    if len(domains) > 0:
        for domain in domains:
            domainid = domain.ident.split('/')[-2].replace('-', '_')
            translations = db.Branch.objects.filter (type='Translation', parent=domain)
            cont = pulse.html.ContainerBox ()
            cont.set_id ('po_' + domainid)
            if len(domains) > 1:
                cont.set_title (pulse.utils.gettext ('%s (%s)')
                                % (domain.title, translations.count()))
            cont.set_sortable_tag ('tr')
            cont.set_sortable_class ('po_' + domainid)
            cont.add_sort_link ('title', pulse.utils.gettext ('lang'), 1)
            cont.add_sort_link ('percent', pulse.utils.gettext ('percent'))
            div = pulse.html.AjaxBox (module.pulse_url + '?ajax=domain&domain=' +
                                      urllib.quote (domain.ident))
            cont.add_content (div)
            box.add_content (cont)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No domains') ))
    return box


def get_developers_box (module):
    box = pulse.html.SidebarBox (title=pulse.utils.gettext ('Developers'))
    rels = db.ModuleEntity.get_related (subj=module)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
            db.Entity.set_cached (rel.pred.id, rel.pred)
        for person in pulse.utils.attrsorted (people.keys(), 'title'):
            lbox = box.add_link_box (person)
            rel = people[person]
            if rel.maintainer:
                lbox.add_badge ('maintainer')
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No developers') ))
    return box


def get_component_info_box (module, branchtype, title):
    objs = module.select_children (branchtype)
    objs = pulse.utils.attrsorted (list(objs), 'title')
    if len(objs) > 0:
        box = pulse.html.InfoBox (title)
        for obj in objs:
            lbox = box.add_link_box (obj)
            doc = db.Documentation.get_related (subj=obj)
            try:
                doc = doc[0]
                lbox.add_fact (pulse.utils.gettext ('docs'), doc.pred)
            except IndexError:
                pass
        return box
    return None


def get_commits_div (module, revs, title):
    div = pulse.html.Div (widget_id='commits')
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
        person = db.Entity.get_cached (rev.person_id)
        span.add_content (pulse.html.Link (person))
        dl.add_term (span)
        dl.add_entry (pulse.html.PopupLink.from_revision (rev, branch=module))
    return div
