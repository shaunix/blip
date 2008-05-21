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
        return output_set (rset, **kw)
    except IndexError:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Set Not Found')
        kw['pages'] = [('set', pulse.utils.gettext ('Sets'))]
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the Set %s') % path[1],
            **kw)
        page.output(fd=fd)
        return 404


def synopsis ():
    """Construct an info box for the front page"""
    box = pulse.html.InfoBox ('sets', pulse.utils.gettext ('Sets'))
    sets = db.ReleaseSet.objects.filter (parent__isnull=True)
    sets = pulse.utils.attrsorted (list(sets), 'title')
    for rset in sets:
        lbox = box.add_link_box (rset)
        lbox.set_show_icon (False)
        subsets = pulse.utils.attrsorted (rset.subsets.all(), ['title'])
        if len(subsets) > 0:
            dl = pulse.html.DefinitionList ()
            lbox.add_content (dl)
            for subset in subsets:
                dl.add_entry (pulse.html.Link (subset))
        else:
            add_set_info (rset, lbox)
    return box


def output_top (**kw):
    """Output a page showing all release sets"""
    page = pulse.html.Page (http=kw.get('http', True))
    page.set_title (pulse.utils.gettext ('Sets'))
    cont = pulse.html.ContainerBox ()
    page.add_content (cont)

    sets = db.ReleaseSet.objects.filter (parent__isnull=True)
    sets = pulse.utils.attrsorted (list(sets), 'title')
    for rset in sets:
        lbox = cont.add_link_box (rset)
        lbox.set_show_icon (False)
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

    tabbed = pulse.html.TabbedBox ()
    page.add_content (tabbed)

    page.set_sublinks_divider (pulse.html.TRIANGLE)
    page.add_sublink (pulse.config.web_root + 'set', pulse.utils.gettext ('Sets'))
    for superset in get_supersets (rset):
        page.add_sublink (superset.pulse_url, superset.title)

    subsets = pulse.utils.attrsorted (rset.subsets.all(), ['title'])
    if len(subsets) > 0:
        if len(path) < 3 or path[2] == 'set':
            cont = pulse.html.ContainerBox ()
            cont.set_columns (2)
            tabbed.add_tab (True, pulse.utils.gettext ('Subsets (%i)') % len(subsets))
            tabbed.add_content (cont)
            for subset in subsets:
                lbox = cont.add_link_box (subset)
                lbox.set_url (None)
                lbox.set_show_icon (False)
                add_set_info (subset, lbox)
        else:
            tabbed.add_tab (rset.pulse_url + '/set',
                            pulse.utils.gettext ('Subsets (%i)') % len(subsets))

    count = False
    if len(path) == 2:
        if len(subsets) > 0:
            count = True
    elif path[2] != 'mod':
        count = True

    if count:
        modcnt = db.SetModule.count_related (subj=rset)
        if modcnt > 0 or len(subsets) == 0:
            tabbed.add_tab (rset.pulse_url + '/mod',
                            pulse.utils.gettext ('Modules (%i)') % modcnt)
    else:
        mods = [mod.pred for mod in db.SetModule.get_related (subj=rset)]
        mods = pulse.utils.attrsorted (mods, 'title')
        modcnt = len(mods)
        cont = pulse.html.ContainerBox ()
        cont.add_sort_link ('title', pulse.utils.gettext ('title'), False)
        cont.add_sort_link ('module', pulse.utils.gettext ('module'))
        cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
        cont.add_sort_link ('score', pulse.utils.gettext ('score'))
        tabbed.add_tab (True, pulse.utils.gettext ('Modules (%i)') % modcnt)
        tabbed.add_content (cont)
        for i in range(modcnt):
            mod = mods[i]
            lbox = cont.add_link_box (mod)
            lbox.add_graph (pulse.config.graphs_root +
                            '/'.join(mod.ident.split('/')[1:] + ['commits.png']) )
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

    if modcnt > 0:
        add_more_tabs (rset, tabbed, path)

    page.output(fd=kw.get('fd'))

    return 0


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
              (('Application', 'Capplet', 'Applet'),
               pulse.utils.gettext ('%i programs'), 'prog'),
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


def add_more_tabs (rset, tabbed, path):
    """Add various tabs to a release set page"""
    things = ({ 'types'  : 'Document',
                'subs'   : ('*', 'gtk-doc'),
                'tabtxt' : pulse.utils.gettext ('Documents (%i)'),
                'txts'   : (pulse.utils.gettext ('User Documentation (%i)'),
                            pulse.utils.gettext ('Developer Documentation (%i)')),
                'tabext' : 'doc',
                'exts'   : ('user', 'devel'),
                'graphs' : 'commits.png' },
              { 'types'  : 'Domain',
                'tabtxt' : pulse.utils.gettext ('Domains (%i)'),
                'tabext' : 'i18n' },
              { 'types'  : ('Application', 'Capplet', 'Applet'),
                'tabtxt' : pulse.utils.gettext ('Programs (%i)'),
                'txts'   : (pulse.utils.gettext ('Applications (%i)'),
                            pulse.utils.gettext ('Capplets (%i)'),
                            pulse.utils.gettext ('Applets (%i)')),
                'tabext' : 'prog',
                'exts'   : ('prog', 'app', 'capplet', 'applet') },
              { 'types'  : 'Library',
                'tabtxt' : pulse.utils.gettext ('Libraries (%i)'),
                'tabext' : 'lib' }
              )
    for thing in things:
        types = thing['types']
        graphs = thing.get ('graphs', False)
        if len(path) > 2 and path[2] == thing['tabext']:
            if isinstance (types, tuple):
                pad = pulse.html.PaddingBox()
                tabbed.add_content (pad)
                sections = []
                for i in range(len(types)):
                    objs = db.Branch.objects.filter (type=types[i],
                                                     parent__set_module_subjs__subj=rset)
                    objs = pulse.utils.attrsorted (list(objs), 'title')
                    if len(objs) == 0:
                        continue
                    cont = pulse.html.ContainerBox (id=thing['exts'][i],
                                                    title=thing['txts'][i] % len(objs))
                    if not graphs:
                        cont.set_columns (2)
                    pad.add_content (cont)
                    sections.append ((objs, cont))
            elif thing.has_key ('subs'):
                pad = pulse.html.PaddingBox()
                tabbed.add_content (pad)

                subinfo = {}
                subs = thing['subs']
                for i in range(len(subs)):
                    sub = subs[i]
                    cont = pulse.html.ContainerBox (id=thing['exts'][i])
                    if not graphs:
                        cont.set_columns (2)
                    subinfo[sub] = ([], cont)

                objs = db.Branch.objects.filter (type=types, parent__set_module_subjs__subj=rset)
                objs = pulse.utils.attrsorted (list(objs), 'title')
                for obj in objs:
                    subtype = obj.subtype
                    if subinfo.has_key (subtype):
                        subinfo[subtype][0].append (obj)
                    elif subinfo.has_key ('*'):
                        subinfo['*'][0].append (obj)

                sections = []
                for i in range(len(subs)):
                    sub = subs[i]
                    sublen = len(subinfo[sub][0])
                    if sublen == 0:
                        continue
                    subinfo[sub][1].set_title (thing['txts'][i] % sublen)
                    pad.add_content (subinfo[sub][1])
                    sections.append (subinfo[sub])
            else:
                objs = db.Branch.objects.filter (type=types, parent__set_module_subjs__subj=rset)
                objs = pulse.utils.attrsorted (list(objs), 'title')
                cont = pulse.html.ContainerBox ()
                if not graphs:
                    cont.set_columns (2)
                tabbed.add_content (cont)
                sections = [(objs, cont)]

            total = 0
            for objs, cont in sections:
                total += len(objs)
                slink_error = False
                slink_mtime = False
                slink_score = False
                slink_documentation = False
                slink_messages = False
                for i in range(len(objs)):
                    obj = objs[i]
                    lbox = cont.add_link_box (obj)
                    if graphs:
                        if isinstance (graphs, tuple):
                            for graph in graphs:
                                lbox.add_graph (pulse.config.graphs_root +
                                                obj.ident[1:] + '/' + graph)
                        else:
                            lbox.add_graph (pulse.config.graphs_root + obj.ident[1:] + '/' + graphs)
                    if obj.error != None:
                        slink_error = True
                        span = pulse.html.Span (obj.error)
                        span.add_class ('errormsg')
                        lbox.add_fact (pulse.utils.gettext ('error'),
                                       pulse.html.AdmonBox (pulse.html.AdmonBox.error, span))
                    span = pulse.html.Span (obj.branch_module)
                    span.add_class ('module')
                    url = obj.ident.split('/')
                    url = '/'.join(['mod'] + url[2:4] + [url[5]])
                    url = pulse.config.web_root + url
                    lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (url, span))
                    if obj.mod_datetime != None:
                        span = pulse.html.Span (divider=pulse.html.SPACE)
                        # FIXME: i18n, word order, but we want to link person
                        span.add_content (pulse.html.Span(obj.mod_datetime.strftime('%Y-%m-%d %T')))
                        span.add_class ('mtime')
                        if obj.mod_person_id != None:
                            span.add_content (pulse.utils.gettext ('by'))
                            if not people_cache.has_key (obj.mod_person_id):
                                people_cache[obj.mod_person_id] = obj.mod_person
                            person = people_cache[obj.mod_person_id]
                            span.add_content (pulse.html.Link (person))
                        lbox.add_fact (pulse.utils.gettext ('modified'), span)
                        slink_mtime = True
                    if obj.mod_score != None:
                        span = pulse.html.Span(str(obj.mod_score))
                        span.add_class ('score')
                        lbox.add_fact (pulse.utils.gettext ('score'), span)
                        slink_score = True
                    docs = db.Documentation.get_related (subj=obj)
                    for doc in docs:
                        # FIXME: multiple docs look bad and sort poorly
                        doc = doc.pred
                        span = pulse.html.Span(doc.title)
                        span.add_class ('docs')
                        lbox.add_fact (pulse.utils.gettext ('docs'),
                                       pulse.html.Link (doc.pulse_url, span))
                        slink_documentation = True
                    if types == 'Domain':
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
                cont.add_sort_link ('title', pulse.utils.gettext ('title'), False)
                cont.add_sort_link ('module', pulse.utils.gettext ('module'))
                if slink_error:
                    cont.add_sort_link ('errormsg', pulse.utils.gettext ('error'))
                if slink_mtime:
                    cont.add_sort_link ('mtime', pulse.utils.gettext ('modified'))
                if slink_score:
                    cont.add_sort_link ('score', pulse.utils.gettext ('score'))
                if slink_documentation:
                    cont.add_sort_link ('docs', pulse.utils.gettext ('docs'))
                if slink_messages:
                    cont.add_sort_link ('messages', pulse.utils.gettext ('messages'))
            tabbed.add_tab (True, thing['tabtxt'] % total)
        else:
            if isinstance (types, tuple):
                objs = db.Branch.objects.filter (type__in=types,
                                                 parent__set_module_subjs__subj=rset)
            else:
                objs = db.Branch.objects.filter (type=types,
                                                 parent__set_module_subjs__subj=rset)
            cnt = objs.count()
            if cnt > 0:
                tabbed.add_tab (rset.pulse_url + '/' + thing['tabext'],
                                thing['tabtxt'] % cnt)
