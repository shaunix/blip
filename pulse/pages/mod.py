# Copyright (c) 2006-2008  Shaun McCance  <shaunm@gnome.org>
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
import re
import urllib

from storm.expr import *

import pulse.config
import pulse.db
import pulse.graphs
import pulse.html
import pulse.response
import pulse.scm
import pulse.utils

def main (response, path, query):
    ident = u'/' + u'/'.join(path)
    if len(path) == 3:
        branches = list(pulse.db.Branch.select (branchable=ident))
        if len(branches) == 0:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the module %s') % path[2],
                title=pulse.utils.gettext ('Module Not Found'))
            response.set_contents (page)
            return

        branch = [branch for branch in branches if branch.is_default]
        if len(branch) == 0:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find a default branch for the module %s')
                % path[2],
                title=pulse.utils.gettext ('Default Branch Not Found'))
            response.set_contents (page)
            return
        branch = branch[0]
    elif len(path) == 4:
        branch = pulse.db.Branch.get (ident)
        if branch == None:
            page = pulse.html.PageNotFound (
                pulse.utils.gettext ('Pulse could not find the branch %s of the module %s')
                % (path[3], path[2]),
                title=pulse.utils.gettext ('Branch Not Found'))
            response.set_contents (page)
            return
    else:
        # FIXME: redirect to /set or something
        pass

    kw = {'path' : path, 'query' : query}
    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, branch, **kw)
    elif query.get('ajax', None) == 'commits':
        output_ajax_commits (response, branch, **kw)
    elif query.get('ajax', None) == 'domain':
        output_ajax_domain (response, branch, **kw)
    elif query.get('ajax', None) == 'graphmap':
        output_ajax_graphmap (response, branch, **kw)
    elif query.get('ajax', None) == 'revfiles':
        output_ajax_revfiles (response, branch, **kw)
    elif query.has_key ('doap'):
        output_doap_file (response, branch, query.get ('doap'), **kw)
    else:
        output_module (response, branch, **kw)

synopsis_sort = -1
def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.SectionBox (pulse.utils.gettext ('Modules'))
    txt = (pulse.utils.gettext ('Pulse is watching %i branches in %i modules.') %
           (pulse.db.Branch.select (type=u'Module').count(),
            pulse.db.Branch.count_branchables (u'Module') ))
    box.add_content (pulse.html.Div (txt))

    columns = pulse.html.ColumnBox (2)
    box.add_content (columns)

    # FIXME STORM
    modules = pulse.db.Branch.select (type=u'Module').order_by (Desc (pulse.db.Branch.mod_score))
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
            bl.add_link (module.pulse_url, module.branch_title)
        else:
            bl.add_link (module)

    modules = pulse.db.Branch.select (type=u'Module').order_by (Desc (pulse.db.Branch.mod_score_diff))
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
            bl.add_link (module.pulse_url, module.branch_title)
        else:
            bl.add_link (module)
    return box


def output_doap_file (response, module, filename, **kw):
    content = pulse.response.HttpTextPacket ()
    response.set_contents (content)
    #response.http_content_type = 'application/rdf+xml'
    #response.http_content_disposition = 'attachment; filename=%s' % filename

    content.add_text_content (
        '<Project xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"\n' +
        '         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"\n' +
        '         xmlns:foaf="http://xmlns.com/foaf/0.1/"\n' +
        '         xmlns:gnome="http://api.gnome.org/doap-extensions#"\n' +
        '         xmlns="http://usefulinc.com/ns/doap#">\n\n')

    content.add_text_content (
        '  <!--\n'
        '  This is a DOAP template file.  It contains Pulse\'s best guesses at\n'
        '  some basic content.  You should verify the information in this file\n'
        '  and modify anything that isn\'t right.  Add the corrected file to your\n'
        '  source code repository to help tools better understand your project.\n'
        '  -->\n\n')

    content.add_text_content ('  <name xml:lang="en">%s</name>\n'
                              % pulse.response.esc (module.title))
    desc = module.localized_desc
    if desc is not None:
        content.add_text_content ('  <shortdesc xml:lang="en">%s</shortdesc>\n'
                                  % pulse.response.esc (desc))
    else:
        content.add_text_content (
            '  <!-- Description, e.g.\n' +
            '       "Falling blocks game"\n' +
            '       "Internationalized text layout and rendering library"\n' +
            '  <shortdesc xml:lang="en">FIXME</shortdesc>\n' +
            '  -->\n')
    content.add_text_content (
        '  <!--\n' + 
        '  <homepage rdf:resource="http://www.gnome.org/" />\n' +
        '  -->\n')
    content.add_text_content (
        '  <!--\n' + 
        '  <mailing-list rdf:resource="http://mail.gnome.org/mailman/listinfo/desktop-devel-list" />\n' +
        '  -->\n')

    if module.data.has_key ('tarname'):
        content.add_text_content (
            '  <download-page rdf:resource="http://download.gnome.org/sources/%s/" />\n'
            % module.data['tarname'])
    else:
        content.add_text_content (
            '  <!--\n' + 
            '  <download-page rdf:resource="http://download.gnome.org/sources/FIXME/" />\n'
            '  -->\n')
    content.add_text_content (
        '  <bug-database rdf:resource="http://bugzilla.gnome.org/browse.cgi?product=%s" />\n'
        % module.scm_module)

    rels = pulse.db.SetModule.get_related (pred=module)
    group = None
    bindings = re.compile ('.*-bindings-.*')
    for rel in rels:
        if bindings.match (rel.subj.ident):
            group = 'bindings'
            break
        elif rel.subj.ident.endswith ('-desktop'):
            group = 'desktop'
            break
        elif rel.subj.ident.endswith ('-devtools'):
            group = 'development'
            break
        elif rel.subj.ident.endswith ('-infrastructure'):
            group = 'infrastructure'
            break
        elif rel.subj.ident.endswith ('-platform'):
            group = 'platform'
            break
    content.add_text_content (
        '\n  <!-- DOAP category: This is used to categorize repositories in cgit.\n'
        )
    if group is None:
        content.add_text_content (
            '       Pulse could not find an appropriate category for this repository.\n' +
            '       Set the rdf:resource attribute with one of the following:\n')
    else:
        content.add_text_content (
            '       Pulse has taken its best guess at the correct category.  You may\n' +
            '       want to replace the rdf:resource attribute with one of the following:\n')
    content.add_text_content (
        '         http://api.gnome.org/doap-extensions#admin\n' +
        '         http://api.gnome.org/doap-extensions#bindings\n' +
        '         http://api.gnome.org/doap-extensions#deprecated\n' +
        '         http://api.gnome.org/doap-extensions#desktop\n' +
        '         http://api.gnome.org/doap-extensions#development\n' +
        '         http://api.gnome.org/doap-extensions#infrastructure\n' +
        '         http://api.gnome.org/doap-extensions#platform\n' +
        '         http://api.gnome.org/doap-extensions#productivity\n')
    if group is None:
        content.add_text_content (
            '  <category rdf:resource="FIXME" />\n' +
            '  -->\n')
    else:
        content.add_text_content ('  -->\n')
        content.add_text_content (
            '  <category rdf:resource="http://api.gnome.org/doap-extensions#%s" />\n'
            % group)

    content.add_text_content ('\n')
    rels = pulse.db.ModuleEntity.get_related (subj=module)
    regexp = re.compile ('^/person/(.*)@gnome.org$')
    for rel in rels:
        if not rel.maintainer:
            continue
        content.add_text_content (
            '  <maintainer>\n' +
            '    <foaf:Person>\n')
        content.add_text_content ('      <foaf:name>%s</foaf:name>\n'
                                  % pulse.response.esc (rel.pred.title))
        if rel.pred.email is not None:
            content.add_text_content ('      <foaf:mbox rdf:resource="%s" />\n'
                                      % pulse.response.esc (rel.pred.email))
        match = regexp.match (rel.pred.ident)
        if match:
            content.add_text_content ('      <gnome:userid>%s</gnome:userid>\n'
                                      % match.group (1))
        content.add_text_content (
            '    </foaf:Person>\n'
            '  </maintainer>\n')

    content.add_text_content ('</Project>\n')


def output_module (response, module, **kw):
    branchable = module.branchable

    page = pulse.html.Page (module)
    response.set_contents (page)

    branches = pulse.utils.attrsorted (list(pulse.db.Branch.select (branchable=module.branchable)),
                                       '-is_default', 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != module.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    if module.data.has_key ('screenshot'):
        page.add_screenshot (module.data['screenshot'])

    page.add_tab ('info', pulse.utils.gettext ('Info'))
    box = get_info_tab (module, **kw)
    page.add_to_tab ('info', box)

    # Developers
    box = get_developers_box (module)
    page.add_sidebar_content (box)

    page.add_tab ('activity', pulse.utils.gettext ('Activity'))
    page.add_tab ('components', pulse.utils.gettext ('Components'))
    if module.select_children (u'Domain').count() > 0:
        page.add_tab ('translations', pulse.utils.gettext ('Translations'))

    # Dependencies
    deps = pulse.db.ModuleDependency.get_related (subj=module)
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


def output_ajax_tab (response, module, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'info':
        response.set_contents (get_info_tab (module, **kw))
    elif tab == 'activity':
        response.set_contents (get_activity_tab (module, **kw))
    elif tab == 'components':
        response.set_contents (get_components_tab (module, **kw))
    elif tab == 'translations':
        response.set_contents (get_translations_tab (module, **kw))


def output_ajax_domain (response, module, **kw):
    query = kw.get ('query', {})
    ident = query.get('domain', None)

    domain = pulse.db.Branch.get (ident)
    domainid = domain.ident.split('/')[-2].replace('-', '_')
    translations = pulse.db.Branch.select_with_statistic (u'Messages',
                                                          type=u'Translation',
                                                          parent=domain)
    translations = pulse.utils.attrsorted (list(translations), (0, 'title'))
    pagediv = pulse.html.Div ()
    response.set_contents (pagediv)
    pad = pulse.html.PaddingBox ()
    pagediv.add_content (pad)

    if domain.error is not None:
        pad.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.error, domain.error))

    if domain.scm_dir == 'po':
        potfile = domain.scm_module + '.pot'
    else:
        potfile = domain.scm_dir + '.pot'
    of = pulse.db.OutputFile.select (type=u'l10n', ident=domain.ident, filename=potfile)
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
        for translation, statistic in translations:
            span = pulse.html.Span (translation.scm_file[:-3])
            span.add_class ('title')
            link = pulse.html.Link (translation.pulse_url, span)
            row = [link]
            percent = 0
            stat1 = statistic.stat1
            stat2 = statistic.stat2
            total = statistic.total
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


def output_ajax_graphmap (response, module, **kw):
    query = kw.get ('query', {})
    id = query.get('id')
    num = query.get('num')
    filename = query.get('filename')
    
    of = pulse.db.OutputFile.select (type=u'graphs', ident=module.ident, filename=filename)
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, module.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'),
                                                 count=int(id), num=int(num), map_only=True)
        response.set_contents (graph)
    except IndexError:
        pass


def output_ajax_commits (response, module, **kw):
    query = kw.get ('query', {})
    weeknum = query.get('weeknum', None)
    if weeknum != None:
        weeknum = int(weeknum)
        thisweek = pulse.utils.weeknum ()
        ago = thisweek - weeknum
        revs = pulse.db.Revision.select_revisions (branch=module, weeknum=weeknum)
        cnt = revs.count()
        revs = list(revs[:20])
    else:
        revs = pulse.db.Revision.select_revisions (branch=module,
                                                   week_range=(pulse.utils.weeknum()-52,))
        cnt = revs.count()
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
    div = get_commits_div (module, revs, title)
    response.set_contents (div)


def output_ajax_revfiles (response, module, **kw):
    if module.scm_server.endswith ('/svn/'):
        base = module.scm_server[:-4] + 'viewvc/'
        colon = base.find (':')
        if colon < 0:
            response.http_status = 404
            return
        if base[:colon] != 'http':
            base = 'http' + base[colon:]
        if module.scm_path != None:
            base += module.scm_path
        elif module.scm_branch == 'trunk':
            base += module.scm_module + '/trunk/'
        else:
            base += module.scm_module + '/branches/' + module.scm_branch + '/'

    query = kw.get ('query', {})
    revid = query.get('revid', None)
    revision = pulse.db.Revision.get (revid)
    files = pulse.db.RevisionFile.select (revision=revision)

    mlink = pulse.html.MenuLink (revision.revision, menu_only=True)
    response.set_contents (mlink)
    for file in files:
        url = base + file.filename
        url += '?r1=%s&r2=%s' % (file.prevrev, file.filerev)
        mlink.add_link (url, file.filename)


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

    rels = pulse.db.SetModule.get_related (pred=module)
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
        if module.mod_person_ident != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (module.mod_person))
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

    if module.updated is not None:
        facts.add_fact_divider ()
        facts.add_fact (pulse.utils.gettext ('Last Updated'),
                        module.updated.strftime('%Y-%m-%d %T'))

    doapdiv = pulse.html.Div ()
    div.add_content (doapdiv)
    doaplink = pulse.html.Link (
        module.pulse_url + ('?doap=%s.doap' % module.scm_module),
        'Download DOAP template file',
        icon='download')
    doapdiv.add_content (doaplink)

    return div


def get_activity_tab (module, **kw):
    box = pulse.html.Div ()
    of = pulse.db.OutputFile.select (type=u'graphs', ident=module.ident, filename=u'commits-0.png')
    try:
        of = of[0]
        graph = pulse.html.Graph.activity_graph (of, module.pulse_url, 'commits',
                                                 pulse.utils.gettext ('%i commits'))
        box.add_content (graph)
    except IndexError:
        pass

    revs = pulse.db.Revision.select_revisions (branch=module,
                                               week_range=(pulse.utils.weeknum()-52,))
    cnt = revs.count()
    revs = list(revs[:10])
    title = (pulse.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    div = get_commits_div (module, revs, title)
    box.add_content (div)

    return box


def get_components_tab (module, **kw):
    columns = pulse.html.ColumnBox (2)

    # Programs and Libraries
    for branchtype, title in (
        (u'Application', pulse.utils.gettext ('Applications')),
        (u'Capplet', pulse.utils.gettext ('Capplets')),
        (u'Applet', pulse.utils.gettext ('Applets')),
        (u'Library', pulse.utils.gettext ('Libraries')) ):

        box = get_component_info_box (module, branchtype, title)
        if box != None:
            columns.add_to_column (0, box)

    # Documents
    box = pulse.html.InfoBox (pulse.utils.gettext ('Documents'))
    columns.add_to_column (1, box)
    docs = module.select_children (u'Document')
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
            res = doc.select_children (u'Translation')
            span = pulse.html.Span (str(res.count()))
            span.add_class ('translations')
            lbox.add_fact (pulse.utils.gettext ('translations'), span)
    else:
        box.add_content (pulse.html.AdmonBox (pulse.html.AdmonBox.warning,
                                              pulse.utils.gettext ('No documents') ))

    return columns


def get_translations_tab (module, **kw):
    box = pulse.html.PaddingBox ()
    domains = module.select_children (u'Domain')
    domains = pulse.utils.attrsorted (list(domains), 'title')
    if len(domains) > 0:
        for domain in domains:
            domainid = domain.ident.split('/')[-2].replace('-', '_')
            translations = pulse.db.Branch.select (type=u'Translation', parent=domain)
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
    rels = pulse.db.ModuleEntity.get_related (subj=module)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
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
            doc = pulse.db.Documentation.get_related (subj=obj)
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
        span.add_content (pulse.html.Link (rev.person))
        dl.add_term (span)
        dl.add_entry (pulse.html.PopupLink.from_revision (rev, branch=module))
    return div
