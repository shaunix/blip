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
            subrels = pulse.db.RecordBranchRelation.selectBy (subj=subset, verb='SetModule')
            reslink.add_fact_div (pulse.utils.gettext ('%i modules') % subrels.count())
            documents = 0;
            domains = 0;
            applications = 0;
            applets = 0;
            for subrel in subrels:
                branch = subrel.pred
                documents += pulse.db.Branch.selectBy (parent=branch, type='Document').count()
                domains += pulse.db.Branch.selectBy (parent=branch, type='Domain').count()
                applications += pulse.db.Branch.selectBy (parent=branch, type='Application').count()
                applets += pulse.db.Branch.selectBy (parent=branch, type='Applet').count()
            reslink.add_fact_div (pulse.utils.gettext ('%i documents') % documents)
            reslink.add_fact_div (pulse.utils.gettext ('%i domains') % domains)
            reslink.add_fact_div (pulse.utils.gettext ('%i applications') % applications)
            reslink.add_fact_div (pulse.utils.gettext ('%i applets') % applets)

    rels = pulse.db.RecordBranchRelation.selectBy (subj=set, verb='SetModule')

    page.output(fd=fd)

    return 0
