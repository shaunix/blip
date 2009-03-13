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

"""Output information about release sets"""

import pulse.config
import pulse.db
import pulse.html
import pulse.utils

def main (response, path, query):
    """Output information about release sets"""
    kw = {'path' : path, 'query' : query}
    if len(path) == 1:
        output_top (response, **kw)
        return
    
    ident = '/' + '/'.join(path[:2])
    rset = pulse.db.ReleaseSet.get (ident)
    if rset == None:
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the Set %s') % path[1],
            title = pulse.utils.gettext ('Set Not Found'))
        response.set_contents (page)
        return

    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, rset, **kw)
    else:
        output_set (response, rset, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.SidebarBox (pulse.utils.gettext ('Sets'))
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    sets = pulse.db.ReleaseSet.find (pulse.db.ReleaseSet.parent_ident == None)
    sets = pulse.utils.attrsorted (list(sets), 'title')
    for rset in sets:
        bl.add_link (rset)
    return box


def output_top (response, **kw):
    """Output a page showing all release sets"""
    page = pulse.html.Page ()
    page.set_title (pulse.utils.gettext ('Sets'))
    response.set_contents (page)
    cont = pulse.html.ContainerBox ()
    cont.set_show_icons (False)
    cont.set_columns (2)
    page.add_content (cont)

    sets = pulse.db.ReleaseSet.select (parent=None)
    sets = pulse.utils.attrsorted (list(sets), 'title')
    for rset in sets:
        lbox = cont.add_link_box (rset)
        subsets = pulse.utils.attrsorted (list(rset.subsets), ['title'])
        if len(subsets) > 0:
            bl = pulse.html.BulletList ()
            lbox.add_content (bl)
            for subset in subsets:
                bl.add_link (subset)
        else:
            add_set_info (rset, lbox)


def output_set (response, rset, **kw):
    """Output information about a release set"""
    path = kw.get('path', [])
    page = pulse.html.Page (rset)
    response.set_contents (page)

    page.set_sublinks_divider (pulse.html.TRIANGLE)
    page.add_sublink (pulse.config.web_root + 'set', pulse.utils.gettext ('Sets'))
    for superset in get_supersets (rset):
        page.add_sublink (superset.pulse_url, superset.title)

    # Schedule
    schedule = rset.data.get ('schedule', [])
    if len(schedule) == 0 and rset.parent != None:
        schedule = rset.parent.data.get ('schedule', [])
    if len(schedule) > 0:
        box = pulse.html.SidebarBox (pulse.utils.gettext ('Schedule'))
        cal = pulse.html.Calendar ()
        box.add_content (cal)
        page.add_sidebar_content (box)
        for event in schedule:
            cal.add_event (*event)

    # Links
    links = rset.data.get ('links', [])
    if len(links) == 0 and rset.parent != None:
        links = rset.parent.data.get ('links', [])
    if len(links) > 0:
        box = pulse.html.SidebarBox (pulse.utils.gettext ('Links'))
        box.set_show_icons (False)
        page.add_sidebar_content (box)
        for link in links:
            lbox = box.add_link_box (link[0], link[1])
            lbox.set_description (link[2])


    # Sets
    setcnt = rset.subsets.count()
    if setcnt > 0:
        page.add_tab ('subsets', pulse.utils.gettext ('Subsets (%i)') % setcnt)

    # Modules
    modcnt = pulse.db.SetModule.count_related (subj=rset)
    if modcnt > 0:
        page.add_tab ('modules', pulse.utils.gettext ('Modules (%i)') % modcnt)

        # Documents
        objs = pulse.db.Branch.select (type=u'Document', parent_in_set=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('documents', pulse.utils.gettext ('Documents (%i)') % cnt)

        # Domains
        objs = pulse.db.Branch.select (type=u'Domain', parent_in_set=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('domains', pulse.utils.gettext ('Domains (%i)') % cnt)

        # Programs
        objs = pulse.db.Branch.select (
            pulse.db.Branch.type.is_in ((u'Application', u'Capplet', u'Applet')),
            parent_in_set=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('programs', pulse.utils.gettext ('Programs (%i)') % cnt)

        # Libraries
        objs = pulse.db.Branch.select (type=u'Library', parent_in_set=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('libraries', pulse.utils.gettext ('Libraries (%i)') % cnt)


def output_ajax_tab (response, rset, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'subsets':
        response.set_contents (get_subsets_tab (rset, **kw))
    elif tab == 'modules':
        response.set_contents (get_modules_tab (rset, **kw))
    elif tab == 'documents':
        response.set_contents (get_documents_tab (rset, **kw))
    elif tab == 'domains':
        response.set_contents (get_domains_tab (rset, **kw))
    elif tab == 'programs':
        response.set_contents (get_programs_tab (rset, **kw))
    elif tab == 'libraries':
        response.set_contents (get_libraries_tab (rset, **kw))


def get_subsets_tab (rset, **kw):
    subsets = pulse.utils.attrsorted (list(rset.subsets), ['title'])
    cont = pulse.html.ContainerBox ()
    cont.set_show_icons (False)
    cont.set_columns (2)
    for subset in subsets:
        lbox = cont.add_link_box (subset)
        add_set_info (subset, lbox)
    return cont


def get_modules_tab (rset, **kw):
    mods = pulse.db.Branch.select_with_mod_person (
        pulse.db.Branch.type == u'Module',
        pulse.db.SetModule.pred_ident == pulse.db.Branch.ident,
        pulse.db.SetModule.subj == rset,
        using=pulse.db.SetModule)
    mods = pulse.utils.attrsorted (mods, (0, 'title'))
    modcnt = len(mods)
    cont = pulse.html.ContainerBox (widget_id='c-modules')
    cont.add_sort_link ('title', pulse.utils.gettext ('title'), 1)
    cont.add_sort_link ('module', pulse.utils.gettext ('module'))
    cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    cont.add_sort_link ('score', pulse.utils.gettext ('score'))
    for i in range(modcnt):
        mod = mods[i][0]
        lbox = cont.add_link_box (mod)
        lbox.add_graph (pulse.config.graphs_root +
                        '/'.join(mod.ident.split('/')[1:] + ['commits-tight.png']),
                        width=208, height=40)
        span = pulse.html.Span (mod.branch_module)
        span.add_class ('module')
        lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (mod.pulse_url, span))
        if mod.mod_datetime != None:
            span = pulse.html.Span (divider=pulse.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            span.add_content (pulse.html.Span(mod.mod_datetime.strftime('%Y-%m-%d %T')))
            span.add_class ('mtime')
            if mod.mod_person_ident != None:
                span.add_content (pulse.utils.gettext ('by'))
                span.add_content (pulse.html.Link (mod.mod_person))
            lbox.add_fact (pulse.utils.gettext ('modified'), span)
        if mod.mod_score != None:
            span = pulse.html.Span(str(mod.mod_score))
            span.add_class ('score')
            lbox.add_fact (pulse.utils.gettext ('score'), span)
    return cont


def get_documents_tab (rset, **kw):
    boxes = (
        {'box' : pulse.html.ContainerBox (widget_id='c-user-docs'),
         'cnt' : 0, 'err' : False },
        {'box' : pulse.html.ContainerBox (widget_id='c-devel-docs'),
         'cnt' : 0, 'err' : False }
        )

    docs = pulse.db.Branch.select_with_mod_person (type=u'Document',
                                                   parent_in_set=rset,
                                                   using=pulse.db.SetModule)
    docs = pulse.utils.attrsorted (list(docs), (0, 'title'))
    for doc, person in docs:
        boxid = doc.subtype == 'gtk-doc' and 1 or 0
        lbox = boxes[boxid]['box'].add_link_box (doc)
        boxes[boxid]['cnt'] += 1
        lbox.add_graph (pulse.config.graphs_root + doc.ident[1:] + '/commits-tight.png',
                        width=240, height=40)
        if doc.error != None:
            slink_error = True
            span = pulse.html.Span (doc.error)
            span.add_class ('errormsg')
            lbox.add_fact (pulse.utils.gettext ('error'),
                           pulse.html.AdmonBox (pulse.html.AdmonBox.error, span))
            boxes[boxid]['err'] = True
        span = pulse.html.Span (doc.branch_module)
        span.add_class ('module')
        url = doc.ident.split('/')
        url = '/'.join(['mod'] + url[2:4] + [url[5]])
        url = pulse.config.web_root + url
        lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (url, span))
        if doc.mod_datetime != None:
            span = pulse.html.Span (divider=pulse.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            span.add_content (pulse.html.Span(doc.mod_datetime.strftime('%Y-%m-%d %T')))
            span.add_class ('mtime')
            if doc.mod_person_ident != None:
                span.add_content (pulse.utils.gettext ('by'))
                span.add_content (pulse.html.Link (doc.mod_person))
            lbox.add_fact (pulse.utils.gettext ('modified'), span)
        if doc.mod_score != None:
            span = pulse.html.Span(str(doc.mod_score))
            span.add_class ('score')
            lbox.add_fact (pulse.utils.gettext ('score'), span)
        lbox.add_fact (pulse.utils.gettext ('status'),
                       pulse.html.StatusSpan (doc.data.get('status')))

    pad = pulse.html.PaddingBox()
    for boxid in (0, 1):
        if boxes[boxid]['cnt'] > 0:
            if boxid == 0:
                boxes[boxid]['box'].set_title (
                    pulse.utils.gettext ('User Documentation (%i)') % boxes[boxid]['cnt'])
            else:
                boxes[boxid]['box'].set_title (
                    pulse.utils.gettext ('Developer Documentation (%i)') % boxes[boxid]['cnt'])
            boxes[boxid]['box'].add_sort_link ('title', pulse.utils.gettext ('title'), 1)
            if boxes[boxid]['err']:
                boxes[boxid]['box'].add_sort_link ('errormsg', pulse.utils.gettext ('error'))
            boxes[boxid]['box'].add_sort_link ('mtime', pulse.utils.gettext ('modified'))
            boxes[boxid]['box'].add_sort_link ('score', pulse.utils.gettext ('score'))
            boxes[boxid]['box'].add_sort_link ('status', pulse.utils.gettext ('status'))
        pad.add_content (boxes[boxid]['box'])
    return pad


def get_domains_tab (rset, **kw):
    objs = pulse.db.Branch.select (type=u'Domain', parent_in_set=rset)
    objs = pulse.utils.attrsorted (list(objs), 'title')
    cont = pulse.html.ContainerBox (widget_id='c-domains')
    cont.set_columns (2)
    slink_error = False

    for obj in objs:
        lbox = cont.add_link_box (obj)
        if obj.error != None:
            slink_error = True
            span = pulse.html.Span (obj.error)
            span.add_class ('errormsg')
            lbox.add_fact (pulse.utils.gettext ('error'),
                           pulse.html.AdmonBox (pulse.html.AdmonBox.error, span))
            slink_error = True
        span = pulse.html.Span (obj.branch_module)
        span.add_class ('module')
        url = obj.ident.split('/')
        url = '/'.join(['mod'] + url[2:4] + [url[5]])
        url = pulse.config.web_root + url
        lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (url, span))
        if obj.scm_dir == 'po':
            potfile = obj.scm_module + '.pot'
        else:
            potfile = obj.scm_dir + '.pot'
        of = pulse.db.OutputFile.select (type=u'l10n',
                                         ident=obj.ident,
                                         filename=potfile)
        try:
            of = of[0]
            span = pulse.html.Span (str(of.statistic))
            span.add_class ('messages')
            lbox.add_fact (pulse.utils.gettext ('messages'), span)
            slink_messages = True
        except IndexError:
            pass

    cont.add_sort_link ('title', pulse.utils.gettext ('title'), 1)
    if slink_error:
        cont.add_sort_link ('errormsg', pulse.utils.gettext ('error'))
    cont.add_sort_link ('module', pulse.utils.gettext ('module'))
    cont.add_sort_link ('messages', pulse.utils.gettext ('messages'))
    return cont


def get_programs_tab (rset, **kw):
    pad = pulse.html.PaddingBox()
    for widget_id, type, title in (
        ('c-applications', u'Application', pulse.utils.gettext ('Applications (%i)')),
        ('c-capplets', u'Capplet', pulse.utils.gettext ('Control Panels (%i)')),
        ('c-applets',u'Applet', pulse.utils.gettext ('Panel Applets (%i)')) ):
        objs = pulse.db.Branch.select (type=type, parent_in_set=rset)
        objs = pulse.utils.attrsorted (list(objs), 'title')
        if len(objs) == 0:
            continue
        cont = pulse.html.ContainerBox (widget_id=widget_id)
        cont.set_title (title % len(objs))
        cont.set_columns (2)
        slink_docs = False
        slink_error = False
        for obj in objs:
            lbox = cont.add_link_box (obj)
            if obj.error != None:
                slink_error = True
                span = pulse.html.Span (obj.error)
                span.add_class ('errormsg')
                lbox.add_fact (pulse.utils.gettext ('error'),
                               pulse.html.AdmonBox (pulse.html.AdmonBox.error, span))
                slink_error = True
            span = pulse.html.Span (obj.branch_module)
            span.add_class ('module')
            url = obj.ident.split('/')
            url = '/'.join(['mod'] + url[2:4] + [url[5]])
            url = pulse.config.web_root + url
            lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (url, span))
            docs = pulse.db.Documentation.get_related (subj=obj)
            for doc in docs:
                # FIXME: multiple docs look bad and sort poorly
                doc = doc.pred
                span = pulse.html.Span(doc.title)
                span.add_class ('docs')
                lbox.add_fact (pulse.utils.gettext ('docs'),
                               pulse.html.Link (doc.pulse_url, span))
                slink_docs = True
        cont.add_sort_link ('title', pulse.utils.gettext ('title'), 1)
        if slink_error:
            cont.add_sort_link ('errormsg', pulse.utils.gettext ('error'))
        if slink_docs:
            cont.add_sort_link ('docs', pulse.utils.gettext ('docs'))
        cont.add_sort_link ('module', pulse.utils.gettext ('module'))
        pad.add_content (cont)
    return pad


def get_libraries_tab (rset, **kw):
    objs = pulse.db.Branch.select (type=u'Library', parent_in_set=rset)
    objs = pulse.utils.attrsorted (list(objs), 'title')
    cont = pulse.html.ContainerBox (widget_id='c-libraries')
    cont.set_columns (2)
    slink_docs = False
    slink_error = False
    for obj in objs:
        lbox = cont.add_link_box (obj)
        if obj.error != None:
            slink_error = True
            span = pulse.html.Span (obj.error)
            span.add_class ('errormsg')
            lbox.add_fact (pulse.utils.gettext ('error'),
                           pulse.html.AdmonBox (pulse.html.AdmonBox.error, span))
            slink_error = True
        span = pulse.html.Span (obj.branch_module)
        span.add_class ('module')
        url = obj.ident.split('/')
        url = '/'.join(['mod'] + url[2:4] + [url[5]])
        url = pulse.config.web_root + url
        lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (url, span))
        docs = pulse.db.Documentation.get_related (subj=obj)
        for doc in docs:
            # FIXME: multiple docs look bad and sort poorly
            doc = doc.pred
            span = pulse.html.Span(doc.title)
            span.add_class ('docs')
            lbox.add_fact (pulse.utils.gettext ('docs'),
                           pulse.html.Link (doc.pulse_url, span))
            slink_docs = True
    cont.add_sort_link ('title', pulse.utils.gettext ('title'), 1)
    if slink_error:
        cont.add_sort_link ('errormsg', pulse.utils.gettext ('error'))
    if slink_docs:
        cont.add_sort_link ('docs', pulse.utils.gettext ('docs'))
    cont.add_sort_link ('module', pulse.utils.gettext ('module'))
    return cont


def add_set_info (rset, lbox):
    cnt = pulse.db.SetModule.count_related (subj=rset)
    if cnt > 0:
        bl = pulse.html.BulletList ()
        lbox.add_content (bl)
        bl.add_link (rset.pulse_url + '#modules',
                     pulse.utils.gettext ('%i modules') % cnt)
    else:
        return

    # Documents
    cnt = pulse.db.Branch.select (type=u'Document', parent_in_set=rset)
    cnt = cnt.count()
    if cnt > 0:
        bl.add_link (rset.pulse_url + '#documents',
                     pulse.utils.gettext ('%i documents') % cnt)

    # Domains
    cnt = pulse.db.Branch.select (type=u'Domain', parent_in_set=rset)
    cnt = cnt.count()
    if cnt > 0:
        bl.add_link (rset.pulse_url + '#domains',
                     pulse.utils.gettext ('%i domains') % cnt)

    # Programs
    objs = pulse.db.Branch.select (
        pulse.db.Branch.type.is_in ((u'Application', u'Capplet', u'Applet')),
        parent_in_set=rset)
    cnt = objs.count()
    if cnt > 0:
        bl.add_link (rset.pulse_url + '#programs',
                     pulse.utils.gettext ('%i programs') % cnt)

    # Libraries
    cnt = pulse.db.Branch.select (type=u'Library', parent_in_set=rset)
    cnt = cnt.count()
    if cnt > 0:
        bl.add_link (rset.pulse_url + '#libraries',
                     pulse.utils.gettext ('%i libraries') % cnt)


def get_supersets (rset):
    """Get a list of the supersets of a release set"""
    superset = rset.parent
    if superset == None:
        return []
    else:
        supers = get_supersets (superset)
        return supers + [superset]
