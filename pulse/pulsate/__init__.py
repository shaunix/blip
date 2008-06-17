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

import datetime
import os.path

import pulse.graphs
import pulse.models as db
import pulse.utils

def update_graphs (obj, select, max, **kw):
    now = datetime.datetime.now()
    thisweek = pulse.utils.weeknum (datetime.datetime.utcnow())
    numweeks = kw.get('numweeks', 104)
    i = 0
    while True:
        topweek = thisweek - (i * numweeks)
        revs = db.Revision.select_revisions (weeknum__gt=(topweek - numweeks),
                                             weeknum__lte=topweek,
                                             **select)
        if revs.count() == 0:
            if i == 1:
                graph_t = pulse.graphs.BarGraph (([0] * numweeks) + stats0,
                                                 max, height=40, tight=True)
                graph_t.save (os.path.join (os.path.dirname (of.get_file_path()), 'commits-tight.png'))
            break;

        fname = 'commits-' + str(i) + '.png'
        of = db.OutputFile.objects.filter (type='graphs', ident=obj.ident, filename=fname)

        try:
            of = of[0]
        except IndexError:
            of = None

        if i == 0 and of != None:
            if kw.get('timestamps', True):
                lastrev = of.data.get ('lastrev', None)
                weeknum = of.data.get ('weeknum', None)
                if weeknum == thisweek:
                    rev = None
                    if lastrev != None:
                        try:
                            rev = revs[0].id
                        except IndexError:
                            pass
                    if lastrev == rev:
                        pulse.utils.log ('Skipping commit graph for %s' % obj.ident)
                        return
        elif of == None:
            of = db.OutputFile (type='graphs', ident=obj.ident, filename=fname, datetime=now)

        if i == 0:
            pulse.utils.log ('Creating commit graphs for %s' % obj.ident)
        stats = [0] * numweeks
        revs = list(revs)
        for rev in revs:
            idx = rev.weeknum - topweek + numweeks - 1
            stats[idx] += 1
        if i == 0:
            score = pulse.utils.score (stats[numweeks - 26:])
            obj.mod_score = score

        graph = pulse.graphs.BarGraph (stats, max, height=40)
        graph.save (of.get_file_path())

        if i == 0:
            stats0 = stats
        elif i == 1:
            graph_t = pulse.graphs.BarGraph (stats + stats0, max, height=40, tight=True)
            graph_t.save (os.path.join (os.path.dirname (of.get_file_path()), 'commits-tight.png'))

        of.data['coords'] = zip (graph.get_coords(), stats, range(topweek - numweeks + 1, topweek + 1))

        if len(revs) > 0:
            of.data['lastrev'] = revs[0].id
        of.data['weeknum'] = topweek
        of.save()

        i += 1
