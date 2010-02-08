import datetime
import math
import re
import urllib

from pulse import applications, core, db, html, scm, utils

def output_doap_file (response, module, filename, **kw):
    content = pulse.response.HttpTextPacket ()
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
        '         http://api.gnome.org/doap-extensions#productivity\n' +
        '       NOTE: There is an "Other" categorization on cgit, but we do not have a\n' +
        '       DOAP category for it.  If your module does not belong to one of these\n' +
        '       groups, then do not include a category property in your DOAP file.\n'
        )
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
            content.add_text_content ('      <foaf:mbox rdf:resource="mailto:%s" />\n'
                                      % pulse.response.esc (rel.pred.email))
        match = regexp.match (rel.pred.ident)
        if match:
            content.add_text_content ('      <gnome:userid>%s</gnome:userid>\n'
                                      % match.group (1))
        content.add_text_content (
            '    </foaf:Person>\n'
            '  </maintainer>\n')

    content.add_text_content ('</Project>\n')


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
