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
    if sets.count() == 0:
        kw = {'http': http}
        kw['title'] = pulse.utils.gettext ('Set Not Found')
        kw['pages'] = [('set', pulse.utils.gettext ('Sets'))]
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('Pulse could not find the Set %s') % path[1],
            **kw)
        page.output(fd=fd)
        return 404

    set = sets[0]

    return output_set (set, path, query, http, fd)


def output_top (path=[], query=[], http=True, fd=None):
    page = pulse.html.Page (http=http)
    page.set_title (pulse.utils.gettext ('Sets'))
    dl = pulse.html.DefinitionList ()
    page.add_content (dl)

    sets = pulse.db.Record.select (
        pulse.db.RecordRelation.q.subjID == None,
        join=LEFTJOINOn(None, pulse.db.RecordRelation,
                        AND (pulse.db.RecordRelation.q.predID == pulse.db.Record.q.id,
                             pulse.db.RecordRelation.q.verb == 'SetSubset')) )
    for set in sets:
        add_subset (set, dl)

    page.output(fd=fd)

    return 0


def output_set (set, path=[], query=[], http=True, fd=None):
    page = pulse.html.ResourcePage (set, http=http)
    dl = pulse.html.DefinitionList ()
    page.add_content (dl)

    rels = pulse.db.RecordRelation.selectBy (subj=set, verb='SetSubset')
    if rels.count() > 0:
        for rel in pulse.utils.attrsorted (rels, 'pred', 'title'):
            add_subset (rel.pred, dl)
        
    rels = pulse.db.RecordBranchRelation.selectBy (subj=set, verb='SetModule')

    page.output(fd=fd)

    return 0


def add_subset (subset, dl):
    dl.add_term (pulse.html.Link (subset))
    cnt = pulse.db.RecordBranchRelation.selectBy (subj=subset, verb='SetModule')
    cnt = cnt.count()
    dl.add_entry (pulse.utils.gettext ('%i modules') % cnt)
    if cnt == 0: return

    Module = Alias (pulse.db.Branch, 'Module')
    things = (('Document', pulse.utils.gettext ('%i documents'), 'docs'),
              ('Domain', pulse.utils.gettext ('%i domains'), 'i18n'),
              ('Application', pulse.utils.gettext ('%i applications'), 'etc#apps'),
              ('Library', pulse.utils.gettext ('%i libraries'), 'etc#libs'),
              ('Applet', pulse.utils.gettext ('%i applets'), 'etc#applets')
              )
    for type, txt, ext in things:
        cnt = pulse.db.Branch.select (
            AND(pulse.db.Branch.q.type == type,
                pulse.db.RecordBranchRelation.q.subjID == subset.id),
            join=LEFTJOINOn(Module, pulse.db.RecordBranchRelation,
                            AND(pulse.db.Branch.q.parentID == Module.q.id,
                                Module.q.id == pulse.db.RecordBranchRelation.q.predID)) )
        cnt = cnt.count()
        if cnt > 0:
            dl.add_entry (pulse.html.Link (subset.pulse_url + '/' + ext, txt % cnt))

