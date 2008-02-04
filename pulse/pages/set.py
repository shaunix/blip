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

import os

import pulse.config
import pulse.html
import pulse.models as db
import pulse.utils

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 1:
        return output_top (path=path, query=query, http=http, fd=fd)
    
    ident = '/' + '/'.join(path[:2])
    sets = db.Record.objects.filter (ident=ident)
    try:
        set = sets[0]
        return output_set (set, path, query, http, fd)
    except IndexError:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Set Not Found')
        kw['pages'] = [('set', pulse.utils.gettext ('Sets'))]
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the Set %s') % path[1],
            **kw)
        page.output(fd=fd)
        return 404


def output_top (path=[], query={}, http=True, fd=None):
    page = pulse.html.Page (http=http)
    page.set_title (pulse.utils.gettext ('Sets'))

    # FIXME: this doesn't work.  what does?
    sets = db.Record.objects.filter (type='Set').extra (
        select={'parent_count' : 'SELECT COUNT(*) FROM SetSubset where pred_ID = Record.id'},
        where=['parent_count=0'])
    sets = pulse.utils.attrsorted (list(sets), 'title')
    # We should probably max this a 3 if we get more sets
    columns = pulse.html.ColumnBox (len(sets))
    page.add_content (columns)
    for i in range(len(sets)):
        set = sets[i]
        box = pulse.html.InfoBox ('set', set.title)
        columns.add_to_column (i, box)
        dl = pulse.html.DefinitionList ()
        box.add_content (dl)
        add_set_entries (set, dl)

    page.output(fd=fd)

    return 0


def output_set (set, path=[], query={}, http=True, fd=None):
    page = pulse.html.RecordPage (set, http=http)

    tabbed = pulse.html.TabbedBox ()
    page.add_content (tabbed)

    page.set_sublinks_divider (pulse.html.TRIANGLE)
    page.add_sublink (pulse.config.web_root + 'set', pulse.utils.gettext ('Sets'))
    for super in get_supersets (set):
        page.add_sublink (super.pulse_url, super.title)

    subsets = [rel.pred for rel in db.SetSubset.get_related (subj=set)]
    subsets = pulse.utils.attrsorted (subsets, ['title'])
    if len(subsets) > 0:
        if len(path) < 3 or path[2] == 'set':
            columns = pulse.html.ColumnBox (2)
            tabbed.add_tab (True, pulse.utils.gettext ('Subsets (%i)') % len(subsets))
            tabbed.add_content (columns)
            dls = [columns.add_to_column (i, pulse.html.DefinitionList()) for i in range(2)]
            for subset, col, pos in pulse.utils.split (subsets, 2):
                dl = dls[col]
                dl.add_term (pulse.html.Link (subset))
                add_set_entries (subset, dl)
        else:
            tabbed.add_tab (set.pulse_url + '/set',
                            pulse.utils.gettext ('Subsets (%i)') % len(subsets))

    count = False
    if len(path) == 2:
        if len(subsets) > 0:
            count = True
    elif path[2] != 'mod':
        count = True

    if count:
        modcnt = db.SetModule.count_related (subj=set)
        if modcnt > 0 or len(subsets) == 0:
            tabbed.add_tab (set.pulse_url + '/mod',
                            pulse.utils.gettext ('Modules (%i)') % modcnt)
    else:
        mods = [mod.pred for mod in db.SetModule.get_related (subj=set)]
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
            lbox.add_graph (pulse.config.graphs_root + '/'.join(mod.ident.split('/')[1:] + ['commits.png']))
            span = pulse.html.Span (mod.branch_module)
            span.add_class ('module')
            lbox.add_fact (pulse.utils.gettext ('module'), pulse.html.Link (mod.pulse_url, span))
            if mod.mod_datetime != None:
                span = pulse.html.Span (divider=pulse.html.SPACE)
                # FIXME: i18n, word order, but we want to link person
                span.add_content (pulse.html.Span(mod.mod_datetime.strftime('%Y-%m-%d %T')))
                span.add_class ('mtime')
                if mod.mod_person != None:
                    span.add_content (pulse.utils.gettext ('by'))
                    span.add_content (pulse.html.Link (mod.mod_person))
                lbox.add_fact (pulse.utils.gettext ('modified'), span)
            if mod.mod_score != None:
                span = pulse.html.Span(str(mod.mod_score))
                span.add_class ('score')
                lbox.add_fact (pulse.utils.gettext ('score'), span)

    if modcnt > 0:
        add_more_tabs (set, tabbed, path=path, query=query)

    page.output(fd=fd)

    return 0


def get_supersets (set):
    superset = db.SetSubset.get_one_related (pred=set)
    if superset == None:
        return []
    else:
        supers = get_supersets (superset.subj)
        return supers + [superset.subj]
    

def add_set_entries (set, dl):
    rels = db.SetSubset.get_related (subj=set)
    rels = pulse.utils.attrsorted (rels, ['pred', 'title'])
    if len(rels) > 0:
        for rel in rels:
            subset = rel.pred
            subdl = pulse.html.DefinitionList ()
            subdl.add_term (pulse.html.Link (subset))
            add_set_entries (subset, subdl)
            dl.add_entry (subdl)
        return

    cnt = db.SetModule.count_related (subj=set)
    dl.add_entry (pulse.utils.gettext ('%i modules') % cnt)
    if cnt == 0: return

    things = (('Document', pulse.utils.gettext ('%i documents'), 'doc'),
              ('Domain', pulse.utils.gettext ('%i domains'), 'i18n'),
              (('Application', 'Capplet', 'Applet'),
               pulse.utils.gettext ('%i programs'), 'prog'),
              ('Library', pulse.utils.gettext ('%i libraries'), 'lib')
              )
    for typ, txt, ext in things:
        if isinstance (typ, tuple):
            cnt = db.Branch.objects.filter (type__in=typ, parent__set_module_subjs__subj=set)
        else:
            cnt = db.Branch.objects.filter (type=typ, parent__set_module_subjs__subj=set)
        cnt = cnt.count()
        if cnt > 0:
            dl.add_entry (pulse.html.Link (set.pulse_url + '/' + ext, txt % cnt))


def add_more_tabs (set, tabbed, path=[], query={}):
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
    for d in things:
        types = d['types']
        graphs = d.get ('graphs', False)
        if len(path) > 2 and path[2] == d['tabext']:
            if isinstance (types, tuple):
                pad = pulse.html.PaddingBox()
                tabbed.add_content (pad)
                sections = []
                for i in range(len(types)):
                    objs = db.Branch.objects.filter (type=types[i], parent__set_module_subjs__subj=set)
                    objs = pulse.utils.attrsorted (list(objs), 'title')
                    cont = pulse.html.ContainerBox (id=d['exts'][i],
                                                    title=d['txts'][i] % len(objs))
                    if not graphs:
                        cont.set_columns (2)
                    pad.add_content (cont)
                    sections.append ((objs, cont))
            elif d.has_key ('subs'):
                pad = pulse.html.PaddingBox()
                tabbed.add_content (pad)
                s = {}
                subs = d['subs']
                for i in range(len(subs)):
                    sub = subs[i]
                    cont = pulse.html.ContainerBox (id=d['exts'][i])
                    if not graphs:
                        cont.set_columns (2)
                    pad.add_content (cont)
                    s[sub] = ([], cont)
                objs = db.Branch.objects.filter (type=types, parent__set_module_subjs__subj=set)
                objs = pulse.utils.attrsorted (list(objs), 'title')
                for obj in objs:
                    stype = obj.subtype
                    if s.has_key (stype):
                        s[stype][0].append (obj)
                    elif s.has_key ('*'):
                        s['*'][0].append (obj)
                sections = []
                for i in range(len(subs)):
                    sub = subs[i]
                    s[sub][1].set_title (d['txts'][i] % len(s[sub][0]))
                    sections.append (s[sub])
            else:
                objs = db.Branch.objects.filter (type=types, parent__set_module_subjs__subj=set)
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
                                lbox.add_graph (pulse.config.graphs_root + obj.ident[1:] + '/' + graph)
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
                        if obj.mod_person != None:
                            span.add_content (pulse.utils.gettext ('by'))
                            span.add_content (pulse.html.Link (obj.mod_person))
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
            tabbed.add_tab (True, d['tabtxt'] % total)
        else:
            if isinstance (types, tuple):
                objs = db.Branch.objects.filter (type__in=types, parent__set_module_subjs__subj=set)
            else:
                objs = db.Branch.objects.filter (type=types, parent__set_module_subjs__subj=set)
            cnt = objs.count()
            if cnt > 0:
                tabbed.add_tab (set.pulse_url + '/' + d['tabext'],
                                d['tabtxt'] % cnt)
