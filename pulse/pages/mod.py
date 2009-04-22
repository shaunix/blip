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

from pulse import db, html, scm, utils
import pulse.response as core

class ModuleHandler (core.RequestHandler):
    def initialize (self):
        ident = u'/' + u'/'.join(self.request.path)
        if len(self.request.path) == 3:
            branches = list(db.Branch.select (branchable=ident))
            if len(branches) == 0:
                raise core.RequestHandlerException (
                    utils.gettext ('Module Not Found'),
                    utils.gettext ('Pulse could not find the module %s')
                    % self.request.path[2])
            branch = [branch for branch in branches if branch.is_default]
            if len(branch) == 0:
                raise core.RequestHandlerException (
                    utils.gettext ('Default Branch Not Found'),
                    utils.gettext (
                    'Pulse could not find a default branch for the module %s')
                    % self.request.path[2])
            branch = branch[0]
        elif len(self.request.path) == 4:
            branch = db.Branch.get (ident)
            if branch is None:
                raise core.RequestHandlerException (
                    utils.gettext ('Branch Not Found'),
                    utils.gettext (
                    'Pulse could not find the branch %s of the module %s')
                    % (self.request.path[3], self.request.path[2]))
        else:
            raise core.RequestHandlerExcpeption (
                utils.gettext ('Branch Not Found'),
                utils.gettext ('Pulse could not find the branch %s') % ident)
        self.record = branch

    def handle_request (self):
        self.output_module_page ()

    def output_module_page (self):
        module = self.record
        branchable = module.branchable

        page = html.Page (module)
        self.response.set_contents (page)

        branches = utils.attrsorted (list(db.Branch.select (branchable=module.branchable)),
                                     '-is_default', 'scm_branch')
        if len(branches) > 1:
            for branch in branches:
                if branch.ident != module.ident:
                    page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
                else:
                    page.add_sublink (None, branch.ident.split('/')[-1])

        if module.data.has_key ('screenshot'):
            page.add_screenshot (module.data['screenshot'])

        # FIXME below
        page.add_tab ('info', utils.gettext ('Info'))
        box = html.Div()
        page.add_to_tab ('info', box)

        for name in self.applications.keys():
            app = self.applications[name]
            if app.provides (html.Tab):
                page.add_tab (name, app.get_tab_title ())

        # Developers
        box = get_developers_box (module)
        page.add_sidebar_content (box)

        return



        page.add_tab ('activity', utils.gettext ('Activity'))
        page.add_tab ('components', utils.gettext ('Components'))
        if module.select_children (u'Domain').count() > 0:
            page.add_tab ('translations', utils.gettext ('Translations'))

        # Dependencies
        deps = db.ModuleDependency.get_related (subj=module)
        deps = utils.attrsorted (list(deps), ['pred', 'scm_module'])
        if len(deps) > 0:
            box = html.SidebarBox (utils.gettext ('Dependencies'))
            page.add_sidebar_content (box)
            d1 = html.Div()
            d2 = html.Div()
            box.add_content (d1)
            box.add_content (html.Rule())
            box.add_content (d2)
            for dep in deps:
                div = html.Div ()
                link = html.Link (dep.pred.pulse_url, dep.pred.scm_module)
                div.add_content (link)
                if dep.direct:
                    d1.add_content (div)
                else:
                    d2.add_content (div)


def get_request_handler (request, response):
    return ModuleHandler (request, response)


def main (response, path, query):

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
        pass
        #output_module (response, branch, **kw)

synopsis_sort = -1
def synopsis ():
    """Construct an info box for the front page"""
    box = html.SectionBox (utils.gettext ('Modules'))
    txt = (utils.gettext ('Pulse is watching %i branches in %i modules.') %
           (db.Branch.select (type=u'Module').count(),
            db.Branch.count_branchables (u'Module') ))
    box.add_content (html.Div (txt))

    columns = html.ColumnBox (2)
    box.add_content (columns)

    # FIXME STORM
    modules = db.Branch.select (type=u'Module').order_by (db.Desc (db.Branch.mod_score))
    bl = html.BulletList ()
    bl.set_title (utils.gettext ('Kicking ass and taking names:'))
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

    modules = db.Branch.select (type=u'Module').order_by (db.Desc (db.Branch.mod_score_diff))
    bl = html.BulletList ()
    bl.set_title (utils.gettext ('Recently rocking:'))
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
    content = core.HttpTextPacket ()
    response.set_contents (content)
    response.http_content_type = 'application/rdf+xml'
    response.http_content_disposition = 'attachment; filename=%s' % filename

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
                              % core.esc (module.title))
    desc = module.localized_desc
    if desc is not None:
        content.add_text_content ('  <shortdesc xml:lang="en">%s</shortdesc>\n'
                                  % core.esc (desc))
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

    rels = db.SetModule.get_related (pred=module)
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
    rels = db.ModuleEntity.get_related (subj=module)
    regexp = re.compile ('^/person/(.*)@gnome.org$')
    for rel in rels:
        if not rel.maintainer:
            continue
        content.add_text_content (
            '  <maintainer>\n' +
            '    <foaf:Person>\n')
        content.add_text_content ('      <foaf:name>%s</foaf:name>\n'
                                  % core.esc (rel.pred.title))
        if rel.pred.email is not None:
            content.add_text_content ('      <foaf:mbox rdf:resource="%s" />\n'
                                      % core.esc (rel.pred.email))
        match = regexp.match (rel.pred.ident)
        if match:
            content.add_text_content ('      <gnome:userid>%s</gnome:userid>\n'
                                      % match.group (1))
        content.add_text_content (
            '    </foaf:Person>\n'
            '  </maintainer>\n')

    content.add_text_content ('</Project>\n')




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

    domain = db.Branch.get (ident)
    domainid = domain.ident.split('/')[-2].replace('-', '_')
    translations = db.Branch.select_with_statistic (u'Messages',
                                                    type=u'Translation',
                                                    parent=domain)
    translations = utils.attrsorted (list(translations), (0, 'title'))
    pagediv = html.Div ()
    response.set_contents (pagediv)
    pad = html.PaddingBox ()
    pagediv.add_content (pad)

    if domain.error is not None:
        pad.add_content (html.AdmonBox (html.AdmonBox.error, domain.error))

    if domain.scm_dir == 'po':
        potfile = domain.scm_module + '.pot'
    else:
        potfile = domain.scm_dir + '.pot'
    of = db.OutputFile.select (type=u'l10n', ident=domain.ident, filename=potfile)
    try:
        of = of[0]
        div = html.Div()
        pad.add_content (div)

        linkdiv = html.Div()
        linkspan = html.Span (divider=html.SPACE)
        linkdiv.add_content (linkspan)
        div.add_content (linkdiv)
        linkspan.add_content (html.Link (of.pulse_url,
                                         utils.gettext ('POT file'),
                                         icon='download' ))
        # FIXME: i18n reordering
        linkspan.add_content (utils.gettext ('(%i messages)')
                              % of.statistic)
        linkspan.add_content (utils.gettext ('on %s')
                              % of.datetime.strftime('%Y-%m-%d %T'))
        missing = of.data.get ('missing', [])
        if len(missing) > 0:
            msg = utils.gettext('%i missing files') % len(missing)
            admon = html.AdmonBox (html.AdmonBox.warning, msg, tag='span')
            mdiv = html.Div()
            popup = html.PopupLink (admon, '\n'.join(missing))
            mdiv.add_content (popup)
            div.add_content (mdiv)
    except IndexError:
        pad.add_content (html.AdmonBox (html.AdmonBox.warning,
                                        utils.gettext ('No POT file') ))

    if len(translations) == 0:
        pad.add_content (html.AdmonBox (html.AdmonBox.warning,
                                        utils.gettext ('No translations') ))
    else:
        grid = html.GridBox ()
        pad.add_content (grid)
        for translation, statistic in translations:
            span = html.Span (translation.scm_file[:-3])
            span.add_class ('title')
            link = html.Link (translation.pulse_url, span)
            row = [link]
            percent = 0
            stat1 = statistic.stat1
            stat2 = statistic.stat2
            total = statistic.total
            untranslated = total - stat1 - stat2
            percent = total and math.floor (100 * (float(stat1) / total)) or 0
            span = html.Span ('%i%%' % percent)
            span.add_class ('percent')
            row.append (span)

            row.append (utils.gettext ('%i.%i.%i') %
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
    
    of = db.OutputFile.select (type=u'graphs', ident=module.ident, filename=filename)
    try:
        of = of[0]
        graph = html.Graph.activity_graph (of, module.pulse_url, 'commits',
                                           utils.gettext ('%i commits'),
                                           count=int(id), num=int(num), map_only=True)
        response.set_contents (graph)
    except IndexError:
        pass


def output_ajax_commits (response, module, **kw):
    query = kw.get ('query', {})
    weeknum = query.get('weeknum', None)
    if weeknum != None:
        weeknum = int(weeknum)
        thisweek = utils.weeknum ()
        ago = thisweek - weeknum
        revs = db.Revision.select_revisions (branch=module, weeknum=weeknum)
        cnt = revs.count()
        revs = list(revs[:20])
    else:
        revs = db.Revision.select_revisions (branch=module,
                                             week_range=(utils.weeknum()-52,))
        cnt = revs.count()
        revs = list(revs[:10])
    if weeknum == None:
        title = (utils.gettext('Showing %i of %i commits:')
                 % (len(revs), cnt))
    elif ago == 0:
        title = (utils.gettext('Showing %i of %i commits from this week:')
                 % (len(revs), cnt))
    elif ago == 1:
        title = (utils.gettext('Showing %i of %i commits from last week:')
                 % (len(revs), cnt))
    else:
        title = (utils.gettext('Showing %i of %i commits from %i weeks ago:')
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
    revision = db.Revision.get (revid)
    files = db.RevisionFile.select (revision=revision)

    mlink = html.MenuLink (revision.revision, menu_only=True)
    response.set_contents (mlink)
    for file in files:
        url = base + file.filename
        url += '?r1=%s&r2=%s' % (file.prevrev, file.filerev)
        mlink.add_link (url, file.filename)


def get_info_tab (module, **kw):
    div = html.PaddingBox()

    if module.error != None:
        div.add_content (html.AdmonBox (html.AdmonBox.error, module.error))

    facts = html.FactsTable()
    div.add_content (facts)

    sep = False
    try:
        facts.add_fact (utils.gettext ('Description'),
                        module.localized_desc)
        sep = True
    except:
        pass

    rels = db.SetModule.get_related (pred=module)
    if len(rels) > 0:
        sets = utils.attrsorted ([rel.subj for rel in rels], 'title')
        span = html.Span (*[html.Link(rset) for rset in sets])
        span.set_divider (html.BULLET)
        facts.add_fact (utils.gettext ('Release Sets'), span)
        sep = True

    if sep:
        facts.add_fact_divider ()

    checkout = scm.Checkout.from_record (module, checkout=False, update=False)
    facts.add_fact (utils.gettext ('Location'), checkout.location)

    if module.mod_datetime != None:
        span = html.Span(divider=html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (module.mod_datetime.strftime('%Y-%m-%d %T'))
        if module.mod_person_ident != None:
            span.add_content (' by ')
            span.add_content (html.Link (module.mod_person))
        facts.add_fact (utils.gettext ('Last Modified'), span)

    if module.data.has_key ('tarname'):
        facts.add_fact_divider ()
        facts.add_fact (utils.gettext ('Tarball Name'), module.data['tarname'])
    if module.data.has_key ('tarversion'):
        if not module.data.has_key ('tarname'):
            facts.add_fact_divider ()
        facts.add_fact (utils.gettext ('Version'), module.data['tarversion'])

    facts.add_fact_divider ()
    facts.add_fact (utils.gettext ('Score'), str(module.mod_score))

    if module.updated is not None:
        facts.add_fact_divider ()
        facts.add_fact (utils.gettext ('Last Updated'),
                        module.updated.strftime('%Y-%m-%d %T'))

    doapdiv = html.Div ()
    div.add_content (doapdiv)
    doaplink = html.Link (
        module.pulse_url + ('?doap=%s.doap' % module.scm_module),
        'Download DOAP template file',
        icon='download')
    doapdiv.add_content (doaplink)

    return div


def get_activity_tab (module, **kw):
    box = html.Div ()
    of = db.OutputFile.select (type=u'graphs', ident=module.ident, filename=u'commits-0.png')
    try:
        of = of[0]
        graph = html.Graph.activity_graph (of, module.pulse_url, 'commits',
                                           utils.gettext ('%i commits'))
        box.add_content (graph)
    except IndexError:
        pass

    revs = db.Revision.select_revisions (branch=module,
                                         week_range=(utils.weeknum()-52,))
    cnt = revs.count()
    revs = list(revs[:10])
    title = (utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
    div = get_commits_div (module, revs, title)
    box.add_content (div)

    return box


def get_components_tab (module, **kw):
    columns = html.ColumnBox (2)

    # Programs and Libraries
    for branchtype, title in (
        (u'Application', utils.gettext ('Applications')),
        (u'Capplet', utils.gettext ('Capplets')),
        (u'Applet', utils.gettext ('Applets')),
        (u'Library', utils.gettext ('Libraries')) ):

        box = get_component_info_box (module, branchtype, title)
        if box != None:
            columns.add_to_column (0, box)

    # Documents
    box = html.InfoBox (utils.gettext ('Documents'))
    columns.add_to_column (1, box)
    docs = module.select_children (u'Document')
    docs = utils.attrsorted (list(docs), 'title')
    if len(docs) > 0:
        if len(docs) > 1:
            box.add_sort_link ('title', utils.gettext ('title'), 1)
            box.add_sort_link ('status', utils.gettext ('status'), 0)
            box.add_sort_link ('translations', utils.gettext ('translations'), 0)
        for doc in docs:
            lbox = box.add_link_box (doc)
            lbox.add_fact (utils.gettext ('status'),
                           html.StatusSpan (doc.data.get('status')))
            res = doc.select_children (u'Translation')
            span = html.Span (str(res.count()))
            span.add_class ('translations')
            lbox.add_fact (utils.gettext ('translations'), span)
    else:
        box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                        utils.gettext ('No documents') ))

    return columns


def get_translations_tab (module, **kw):
    box = html.PaddingBox ()
    domains = module.select_children (u'Domain')
    domains = utils.attrsorted (list(domains), 'title')
    if len(domains) > 0:
        for domain in domains:
            domainid = domain.ident.split('/')[-2].replace('-', '_')
            translations = db.Branch.select (type=u'Translation', parent=domain)
            cont = html.ContainerBox ()
            cont.set_id ('po_' + domainid)
            if len(domains) > 1:
                cont.set_title (utils.gettext ('%s (%s)')
                                % (domain.title, translations.count()))
            cont.set_sortable_tag ('tr')
            cont.set_sortable_class ('po_' + domainid)
            cont.add_sort_link ('title', utils.gettext ('lang'), 1)
            cont.add_sort_link ('percent', utils.gettext ('percent'))
            div = html.AjaxBox (module.pulse_url + '?ajax=domain&domain=' +
                                urllib.quote (domain.ident))
            cont.add_content (div)
            box.add_content (cont)
    else:
        box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                        utils.gettext ('No domains') ))
    return box


def get_developers_box (module):
    box = html.SidebarBox (title=utils.gettext ('Developers'))
    rels = db.ModuleEntity.get_related (subj=module)
    if len(rels) > 0:
        people = {}
        for rel in rels:
            people[rel.pred] = rel
        for person in utils.attrsorted (people.keys(), 'title'):
            lbox = box.add_link_box (person)
            rel = people[person]
            if rel.maintainer:
                lbox.add_badge ('maintainer')
    else:
        box.add_content (html.AdmonBox (html.AdmonBox.warning,
                                        utils.gettext ('No developers') ))
    return box


def get_component_info_box (module, branchtype, title):
    objs = module.select_children (branchtype)
    objs = utils.attrsorted (list(objs), 'title')
    if len(objs) > 0:
        box = html.InfoBox (title)
        for obj in objs:
            lbox = box.add_link_box (obj)
            doc = db.Documentation.get_related (subj=obj)
            try:
                doc = doc[0]
                lbox.add_fact (utils.gettext ('docs'), doc.pred)
            except IndexError:
                pass
        return box
    return None
