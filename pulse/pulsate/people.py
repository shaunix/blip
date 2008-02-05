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
import os

import pulse.graphs
import pulse.models as db

synop = 'update information about people'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only people with a matching identifier will be updated.'


def update_person (person, **kw):
    now = datetime.datetime.now()
    thisweek = pulse.utils.weeknum (now)
    of = db.OutputFile.objects.filter (type='graphs', ident=person.ident, filename='commits.png')
    try:
        of = of[0]
    except IndexError:
        of = None

    revs = db.Revision.select_revisions (person=person, filename__isnull=True,
                                         weeknum__gt=(thisweek - 24))

    if of != None:
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
                    pulse.utils.log ('Skipping commit graph for %s' % person.ident)
                    return
    else:
        of = db.OutputFile (type='graphs', ident=person.ident, filename='commits.png', datetime=now)

    pulse.utils.log ('Creating commit graph for %s' % person.ident)
    stats = [0] * 24
    revs = list(revs)
    for rev in revs:
        idx = rev.weeknum - thisweek + 23
        stats[idx] += 1
    score = pulse.utils.score (stats)
    person.mod_score = score
    person.save()

    graph = pulse.graphs.BarGraph (stats, 20)
    graph.save (of.get_file_path())

    of.data['coords'] = zip (graph.get_coords(), stats, range(thisweek-23, thisweek+1))
    if len(revs) > 0:
        of.data['lastrev'] = revs[0].id
    of.data['weeknum'] = thisweek
    of.save()


################################################################################
## main

def main (argv, options={}):
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix == None:
        people = db.Entity.objects.filter (type='Person')
    else:
        people = db.Entity.objects.filter (type='Person', ident__startswith=prefix)
    for person in people:
        update_person (person, timestamps=timestamps)
