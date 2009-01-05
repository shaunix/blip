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
import pulse.html
import pulse.models as db
import pulse.utils

people_cache = {}

def main (path, query, http=True, fd=None):
    """Output information about release sets"""
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    if len(path) == 1:
        return output_top (**kw)
    
    ident = '/' + '/'.join(path[:2])
    sets = db.ReleaseSet.objects.filter (ident=ident)
    try:
        rset = sets[0]
    except IndexError:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Set Not Found')
        kw['pages'] = [('set', pulse.utils.gettext ('Sets'))]
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the Set %s') % path[1],
            **kw)
        page.output(fd=fd)
        return 404

    if query.get('ajax', None) == 'tab':
        return output_ajax_tab (rset, **kw)
    else:
        return output_set (rset, **kw)


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.InfoBox (pulse.utils.gettext ('Sets'))
    div = pulse.html.Div (pulse.utils.gettext ('Pulse is watching the following release sets:'))
    box.add_content (div)
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    sets = db.ReleaseSet.objects.filter (parent__isnull=True)
    sets = pulse.utils.attrsorted (list(sets), 'title')
    for rset in sets:
        bl.add_item (pulse.html.Link (rset))
    return box


def output_top (**kw):
    """Output a page showing all release sets"""
    page = pulse.html.Page (http=kw.get('http', True))
    page.set_title (pulse.utils.gettext ('Sets'))
    cont = pulse.html.ContainerBox ()
    cont.set_show_icons (False)
    page.add_content (cont)

    sets = db.ReleaseSet.objects.filter (parent__isnull=True)
    sets = pulse.utils.attrsorted (list(sets), 'title')
    for rset in sets:
        lbox = cont.add_link_box (rset)
        subsets = pulse.utils.attrsorted (rset.subsets.all(), ['title'])
        if len(subsets) > 0:
            dl = pulse.html.DefinitionList ()
            lbox.add_content (dl)
            for subset in subsets:
                dl.add_entry (pulse.html.Link (subset))
        else:
            add_set_info (rset, lbox)

    page.output(fd=kw.get('fd'))

    return 0


def output_set (rset, **kw):
    """Output information about a release set"""
    path = kw.get('path', [])
    page = pulse.html.RecordPage (rset, http=kw.get('http', True))

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
        page.add_tab ('set', pulse.utils.gettext ('Subsets (%i)') % setcnt)

    # Modules
    modcnt = db.SetModule.count_related (subj=rset)
    if modcnt > 0:
        page.add_tab ('mod', pulse.utils.gettext ('Modules (%i)') % modcnt)

        # Documents
        objs = db.Branch.objects.filter (type='Document',
                                         parent__set_module_subjs__subj=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('doc', pulse.utils.gettext ('Documents (%i)') % cnt)

        # Domains
        objs = db.Branch.objects.filter (type='Domain',
                                         parent__set_module_subjs__subj=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('i18n', pulse.utils.gettext ('Domains (%i)') % cnt)

        # Programs
        objs = db.Branch.objects.filter (type__in=('Application', 'Capplet', 'Applet'),
                                         parent__set_module_subjs__subj=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('prog', pulse.utils.gettext ('Programs (%i)') % cnt)

        # Libraries
        objs = db.Branch.objects.filter (type='Library',
                                         parent__set_module_subjs__subj=rset)
        cnt = objs.count()
        if cnt > 0:
            page.add_tab ('lib', pulse.utils.gettext ('Libraries (%i)') % cnt)

    page.output(fd=kw.get('fd'))

    return 0


def output_ajax_tab (rset, **kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    tab = query.get('tab', None)
    if tab == 'set':
        page.add_content (get_set_box (rset, **kw))
    elif tab == 'mod':
        page.add_content (get_mod_box (rset, **kw))
    elif tab == 'doc':
        page.add_content (get_doc_box (rset, **kw))
    elif tab == 'i18n':
        page.add_content (get_i18n_box (rset, **kw))
    elif tab == 'prog':
        page.add_content (get_prog_box (rset, **kw))
    elif tab == 'lib':
        page.add_content (get_lib_box (rset, **kw))
    page.output(fd=kw.get('fd'))
    return 0


def get_set_box (rset, **kw):
    subsets = pulse.utils.attrsorted (rset.subsets.all(), ['title'])
    cont = pulse.html.ContainerBox ()
    cont.set_show_icons (False)
    cont.set_columns (2)
    for subset in subsets:
        lbox = cont.add_link_box (subset)
        add_set_info (subset, lbox)
    return cont


def get_mod_box (rset, **kw):
    mods = [mod.pred for mod in db.SetModule.get_related (subj=rset)]
    mods = pulse.utils.attrsorted (mods, 'title')
    modcnt = len(mods)
    cont = pulse.html.ContainerBox (id='modules')
    cont.add_sort_link ('title', pulse.utils.gettext ('title'), 1)
    cont.add_sort_link ('module', pulse.utils.gettext ('module'))
    cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
    cont.add_sort_link ('score', pulse.utils.gettext ('score'))
    for i in range(modcnt):
        mod = mods[i]
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
            if mod.mod_person_id != None:
                span.add_content (pulse.utils.gettext ('by'))
                if not people_cache.has_key (mod.mod_person_id):
                    people_cache[mod.mod_person_id] = mod.mod_person
                person = people_cache[mod.mod_person_id]
                span.add_content (pulse.html.Link (person))
            lbox.add_fact (pulse.utils.gettext ('modified'), span)
        if mod.mod_score != None:
            span = pulse.html.Span(str(mod.mod_score))
            span.add_class ('score')
            lbox.add_fact (pulse.utils.gettext ('score'), span)
    return cont


def get_doc_box (rset, **kw):
    boxes = (
        {'box' : pulse.html.ContainerBox (id='userdocs'),
         'cnt' : 0, 'err' : False },
        {'box' : pulse.html.ContainerBox (id='develdocs'),
         'cnt' : 0, 'err' : False }
        )

    docs = db.Branch.objects.filter (type='Document', parent__set_module_subjs__subj=rset)
    docs = pulse.utils.attrsorted (list(docs), 'title')
    for doc in docs:
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
            if doc.mod_person_id != None:
                span.add_content (pulse.utils.gettext ('by'))
                if not people_cache.has_key (doc.mod_person_id):
                    people_cache[doc.mod_person_id] = doc.mod_person
                person = people_cache[doc.mod_person_id]
                span.add_content (pulse.html.Link (person))
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


def get_i18n_box (rset, **kw):
    objs = db.Branch.objects.filter (type='Domain',
                                     parent__set_module_subjs__subj=rset)
    objs = pulse.utils.attrsorted (list(objs), 'title')
    cont = pulse.html.ContainerBox (id='domains')
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
        of = db.OutputFile.objects.filter (type='l10n',
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


def get_prog_box (rset, **kw):
    pad = pulse.html.PaddingBox()
    for id, type, txt in (
        ('applications', 'Application', pulse.utils.gettext ('Applications (%i)')),
        ('capplets', 'Capplet', pulse.utils.gettext ('Control Panels (%i)')),
        ('applets','Applet', pulse.utils.gettext ('Panel Applets (%i)')) ):
        objs = db.Branch.objects.filter (type=type,
                                         parent__set_module_subjs__subj=rset)
        objs = pulse.utils.attrsorted (list(objs), 'title')
        if len(objs) == 0:
            continue
        cont = pulse.html.ContainerBox (id=id)
        cont.set_title (txt % len(objs))
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
            docs = db.Documentation.get_related (subj=obj)
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


def get_lib_box (rset, **kw):
    objs = db.Branch.objects.filter (type='Library',
                                     parent__set_module_subjs__subj=rset)
    objs = pulse.utils.attrsorted (list(objs), 'title')
    cont = pulse.html.ContainerBox (id='libraries')
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
        docs = db.Documentation.get_related (subj=obj)
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


def get_supersets (rset):
    """Get a list of the supersets of a release set"""
    superset = rset.parent
    if superset == None:
        return []
    else:
        supers = get_supersets (superset)
        return supers + [superset]


def add_set_info (rset, lbox):
    """Add information to a release set link box"""
    cnt = db.SetModule.count_related (subj=rset)
    dl = pulse.html.DefinitionList ()
    lbox.add_content (dl)
    dl.add_entry (pulse.html.Link (rset.pulse_url + '/mod',
                                   pulse.utils.gettext ('%i modules') % cnt))
    if cnt == 0:
        return

    things = (('Document', pulse.utils.gettext ('%i documents'), 'doc'),
              ('Domain', pulse.utils.gettext ('%i domains'), 'i18n'),
              ('Library', pulse.utils.gettext ('%i libraries'), 'lib')
              )
    for typ, txt, ext in things:
        if isinstance (typ, tuple):
            cnt = db.Branch.objects.filter (type__in=typ, parent__set_module_subjs__subj=rset)
        else:
            cnt = db.Branch.objects.filter (type=typ, parent__set_module_subjs__subj=rset)
        cnt = cnt.count()
        if cnt > 0:
            dl.add_entry (pulse.html.Link (rset.pulse_url + '/' + ext, txt % cnt))
