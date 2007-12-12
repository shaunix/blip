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

import pulse.config
import pulse.db
import pulse.html
import pulse.utils

from sqlobject.sqlbuilder import *

def main (path=[], query={}, http=True, fd=None):
    if len(path) == 1:
        return output_top (path=path, query=query, http=http, fd=fd)
    
    ident = '/' + '/'.join(path[:2])
    sets = pulse.db.Record.selectBy (ident=ident)
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


def output_top (path=[], query=[], http=True, fd=None):
    page = pulse.html.Page (http=http)
    page.set_title (pulse.utils.gettext ('Sets'))

    sets = pulse.db.Record.select (
        pulse.db.RecordRelation.q.subjID == None,
        join=LEFTJOINOn(None, pulse.db.RecordRelation,
                        AND (pulse.db.RecordRelation.q.predID == pulse.db.Record.q.id,
                             pulse.db.RecordRelation.q.verb == 'SetSubset')) )
    sets = pulse.utils.attrsorted (list(sets), 'title')
    # We should probably max this a 3 if we get more sets
    columns = pulse.html.ColumnBox (len(sets))
    page.add_content (columns)
    for i in range(len(sets)):
        set = sets[i]
        box = pulse.html.InfoBox ('set', set.title)
        columns.add_content (i, box)
        dl = pulse.html.DefinitionList ()
        box.add_content (dl)
        add_set_entries (set, dl)

    page.output(fd=fd)

    return 0


def output_set (set, path=[], query=[], http=True, fd=None):
    page = pulse.html.ResourcePage (set, http=http)

    tabbed = pulse.html.TabbedBox ()
    page.add_content (tabbed)

    page.set_sublinks_divider (page.TRIANGLE)
    page.add_sublink (pulse.config.webroot + 'set', pulse.utils.gettext ('Sets'))
    for super in get_supersets (set):
        page.add_sublink (super.pulse_url, super.title)

    subsets = pulse.db.RecordRelation.selectBy (subj=set, verb='SetSubset')
    subsets = pulse.utils.attrsorted (list(subsets), ['pred', 'title'])
    if len(subsets) > 0:
        if len(path) < 3 or path[2] == 'set':
            columns = pulse.html.ColumnBox (2)
            tabbed.add_tab (pulse.utils.gettext ('Subsets (%i)') % len(subsets), True, columns)
            dls = [columns.add_content (i, pulse.html.DefinitionList()) for i in range(2)]
            for i in range(len(subsets)):
                subset = subsets[i].pred
                dl = dls[int(i > len(subsets) / 2 + 1)]
                dl.add_term (pulse.html.Link (subset))
                add_set_entries (subset, dl)
        else:
            tabbed.add_tab (pulse.utils.gettext ('Subsets (%i)') % len(subsets),
                            False, set.pulse_url + '/set')

    mods = pulse.db.Branch.select (
        pulse.db.RecordBranchRelation.q.subjID == set.id,
        join=INNERJOINOn(None, pulse.db.RecordBranchRelation,
                         pulse.db.Branch.q.id == pulse.db.RecordBranchRelation.q.predID))
    count = False
    if len(path) == 2:
        if len(subsets) > 0:
            count = True
    elif path[2] != 'mod':
        count = True

    if count:
        modcnt = mods.count()
        if modcnt > 0 or len(subsets) == 0:
            tabbed.add_tab (pulse.utils.gettext ('Modules (%i)') % modcnt, False, set.pulse_url + '/mod')
    else:
        mods = pulse.utils.attrsorted (list(mods), 'title')
        modcnt = len(mods)
        lcont = pulse.html.LinkBoxContainer ()
        lcont.set_columns (2)
        lcont.add_sort_link ('title', pulse.utils.gettext ('title'), False)
        lcont.add_sort_link ('mtime', pulse.utils.gettext ('mtime'))
        lcont.add_sort_link ('module', pulse.utils.gettext ('module'))
        tabbed.add_tab (pulse.utils.gettext ('Modules (%i)') % modcnt, True, lcont)
        for i in range(modcnt):
            mod = mods[i]
            lbox = lcont.add_link_box (mod)
            span = pulse.html.Span (mod.branch_module)
            span.add_class ('module')
            lbox.add_fact ('module', pulse.html.Link (mod.pulse_url, span))
            if mod.mod_datetime != None:
                span = pulse.html.Span (divider=pulse.html.Span.SPACE)
                # FIXME: i18n, word order, but we want to link person
                span.add_content (pulse.html.Span(str(mod.mod_datetime.date())))
                span.add_class ('mtime')
                if mod.mod_person != None:
                    span.add_content (pulse.utils.gettext ('by'))
                    span.add_content (pulse.html.Link (mod.mod_person))
                lbox.add_fact (pulse.utils.gettext ('modified'), span)

    if modcnt > 0:
        add_more_tabs (set, tabbed, path=path, query=query)

    page.output(fd=fd)

    return 0


def get_supersets (set):
    supersets=[]
    supersets = pulse.db.Record.select (
        pulse.db.RecordRelation.q.predID == set.id,
        join=INNERJOINOn(None, pulse.db.RecordRelation,
                         AND(pulse.db.RecordRelation.q.subjID == pulse.db.Record.q.id,
                             pulse.db.RecordRelation.q.verb == 'SetSubset')) )
    try:
        superset = supersets[0]
        supers = get_supersets (superset)
        return supers + [superset]
    except IndexError:
        return []
    

def add_set_entries (set, dl):
    rels = pulse.db.RecordRelation.selectBy (subj=set, verb='SetSubset')
    rels = pulse.utils.attrsorted (rels[0:], ['pred', 'title'])
    if len(rels) > 0:
        for rel in rels:
            subset = rel.pred
            subdl = pulse.html.DefinitionList ()
            subdl.add_term (pulse.html.Link (subset))
            add_set_entries (subset, subdl)
            dl.add_entry (subdl)
        return

    cnt = pulse.db.RecordBranchRelation.selectBy (subj=set, verb='SetModule')
    cnt = cnt.count()
    dl.add_entry (pulse.utils.gettext ('%i modules') % cnt)
    if cnt == 0: return

    Module = Alias (pulse.db.Branch, 'Module')
    things = (('Document', pulse.utils.gettext ('%i documents'), 'doc'),
              ('Domain', pulse.utils.gettext ('%i domains'), 'i18n'),
              ('Application', pulse.utils.gettext ('%i applications'), 'app'),
              ('Library', pulse.utils.gettext ('%i libraries'), 'lib'),
              ('Applet', pulse.utils.gettext ('%i applets'), 'applet')
              )
    for type, txt, ext in things:
        cnt = pulse.db.Branch.select (
            AND(pulse.db.Branch.q.type == type,
                pulse.db.RecordBranchRelation.q.subjID == set.id),
            join=LEFTJOINOn(Module, pulse.db.RecordBranchRelation,
                            AND(pulse.db.Branch.q.parentID == Module.q.id,
                                Module.q.id == pulse.db.RecordBranchRelation.q.predID)) )
        cnt = cnt.count()
        if cnt > 0:
            dl.add_entry (pulse.html.Link (set.pulse_url + '/' + ext, txt % cnt))


def add_more_tabs (set, tabbed, path=[], query=[]):
    Module = Alias (pulse.db.Branch, 'Module')

    rels = pulse.db.Branch.select (
        AND(pulse.db.Branch.q.type == 'Document',
            pulse.db.RecordBranchRelation.q.subjID == set.id),
        join=LEFTJOINOn(Module, pulse.db.RecordBranchRelation,
                        AND(pulse.db.Branch.q.parentID == Module.q.id,
                            Module.q.id == pulse.db.RecordBranchRelation.q.predID)) )
    if len(path) > 2 and path[2] == 'doc':
        docs = {'users' : [], 'devels' : []}
        user_docs = []
        devel_docs = []
        cnt = 0
        for doc in pulse.utils.attrsorted (rels, 'title'):
            if doc.subtype == 'gtk-doc':
                docs['devels'].append (doc)
                cnt += 1
            else:
                docs['users'].append (doc)
                cnt += 1
        vbox = pulse.html.VBox()
        for id, txt in (('users', pulse.utils.gettext ('User Documentation (%i)')),
                        ('devels', pulse.utils.gettext ('Developer Documentation (%i)')) ):
            if len(docs[id]) > 0:
                lcont = pulse.html.LinkBoxContainer (id=id)
                lcont.set_title (txt % len(docs[id]))
                lcont.set_columns (2)
                lcont.set_sort_link_class ('doc' + id)
                lcont.add_sort_link ('title', pulse.utils.gettext ('title'), False)
                lcont.add_sort_link ('mtime', pulse.utils.gettext ('mtime'))
                lcont.add_sort_link ('module', pulse.utils.gettext ('module'))
                vbox.add_content (lcont)
                for doc in docs[id]:
                    lbox = lcont.add_link_box (doc)
                    lbox.add_class ('doc' + id)
                    if doc.mod_datetime != None:
                        span = pulse.html.Span (divider=pulse.html.Span.SPACE)
                        # FIXME: i18n, word order, but we want to link person
                        span.add_content (pulse.html.Span(str(doc.mod_datetime.date())))
                        span.add_class ('mtime')
                        if doc.mod_person != None:
                            span.add_content (pulse.utils.gettext ('by'))
                            span.add_content (pulse.html.Link (doc.mod_person))
                        lbox.add_fact (pulse.utils.gettext ('modified'), span)
                    span = pulse.html.Span (doc.branch_module)
                    span.add_class ('module')
                    # FIXME: munge ident to avoid this extra parent SELECT
                    url = doc.ident.split('/')
                    url = '/'.join(['mod'] + url[2:4] + [url[5]])
                    url = pulse.config.webroot + url
                    lbox.add_fact ('module', pulse.html.Link (url, span))
        tabbed.add_tab ('Documents (%i)' % cnt, True, vbox)
    else:
        tabbed.add_tab ('Documents (%i)' % rels.count(), False, set.pulse_url + '/doc')

    things = (('Domain', pulse.utils.gettext ('Domains (%i)'), 'i18n'),
              ('Application', pulse.utils.gettext ('Applications (%i)'), 'app'),
              ('Library', pulse.utils.gettext ('Libraries (%i)'), 'lib'),
              ('Applet', pulse.utils.gettext ('Applets (%i)'), 'applet')
              )
    for type, txt, ext in things:
        rels = pulse.db.Branch.select (
            AND(pulse.db.Branch.q.type == type,
                pulse.db.RecordBranchRelation.q.subjID == set.id),
            join=LEFTJOINOn(Module, pulse.db.RecordBranchRelation,
                            AND(pulse.db.Branch.q.parentID == Module.q.id,
                                Module.q.id == pulse.db.RecordBranchRelation.q.predID)) )
        if len(path) > 2 and path[2] == ext:
            rels = pulse.utils.attrsorted (list(rels), 'title', 'scm_module')
            lcont = pulse.html.LinkBoxContainer ()
            lcont.set_columns (2)
            slink_mtime = False
            slink_documentation = False
            tabbed.add_tab (txt % len(rels), True, lcont)
            for i in range(len(rels)):
                rel = rels[i]
                lbox = lcont.add_link_box (rel)
                span = pulse.html.Span (rel.branch_module)
                span.add_class ('module')
                url = rel.ident.split('/')
                url = '/'.join(['mod'] + url[2:4] + [url[5]])
                url = pulse.config.webroot + url
                lbox.add_fact ('module', pulse.html.Link (url, span))
                doc = pulse.db.Branch.select (
                    (pulse.db.BranchRelation.q.verb == (type + 'Document')) &
                    (pulse.db.BranchRelation.q.subjID == rel.id),
                    join=INNERJOINOn (None, pulse.db.BranchRelation,
                                      pulse.db.BranchRelation.q.predID == pulse.db.Branch.q.id) )
                try:
                    doc = doc[0]
                    span = pulse.html.Span(doc.title)
                    span.add_class ('docs')
                    lbox.add_fact (pulse.utils.gettext ('docs'),
                                   pulse.html.Link (doc.pulse_url, span))
                    slink_documentation = True
                except IndexError:
                    pass
            lcont.add_sort_link ('title', pulse.utils.gettext ('title'), False)
            if slink_mtime:
                lcont.add_sort_link ('mtime', pulse.utils.gettext ('mtime'))
            lcont.add_sort_link ('module', pulse.utils.gettext ('module'))
            if slink_documentation:
                lcont.add_sort_link ('docs', pulse.utils.gettext ('docs'))
        else:
            cnt = rels.count()
            if cnt > 0:
                tabbed.add_tab (txt % cnt, False, set.pulse_url + '/' + ext)
