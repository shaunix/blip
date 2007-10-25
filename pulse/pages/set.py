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
    # FIXME: path == [] -> show all top-level sets
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


def output_set (set, path=[], query=[], http=True, fd=None):
    page = pulse.html.ResourcePage (set, http=http)

    rels = pulse.db.RecordRelation.selectBy (subj=set, verb='SetSubset')
    if rels.count() > 0:
        for rel in pulse.utils.attrsorted (rels, 'pred', 'title'):
            subset = rel.pred
            reslink = pulse.html.ResourceLinkBox (subset)
            page.add_content (reslink)
            cnt = pulse.db.RecordBranchRelation.selectBy (subj=subset, verb='SetModule')
            cnt = cnt.count()
            reslink.add_fact_div (pulse.utils.gettext ('%i modules') % cnt)
            if cnt == 0: continue

            Module = Alias (pulse.db.Branch, 'Module')
            things = (('Document', pulse.utils.gettext ('%i documents')),
                      ('Domain', pulse.utils.gettext ('%i domains')),
                      ('Application', pulse.utils.gettext ('%i applications')),
                      ('Library', pulse.utils.gettext ('%i libraries')),
                      ('Applet', pulse.utils.gettext ('%i applets'))
                      )
            for type, txt in things:
                cnt = pulse.db.Branch.select (
                    AND(pulse.db.Branch.q.type == type,
                        pulse.db.RecordBranchRelation.q.subjID == subset.id),
                    join=LEFTJOINOn(Module, pulse.db.RecordBranchRelation,
                                    AND(pulse.db.Branch.q.parentID == Module.q.id,
                                        Module.q.id == pulse.db.RecordBranchRelation.q.predID)) )
                cnt = cnt.count()
                if cnt > 0:
                    reslink.add_fact_div (txt % cnt)

    rels = pulse.db.RecordBranchRelation.selectBy (subj=set, verb='SetModule')

    page.output(fd=fd)

    return 0
