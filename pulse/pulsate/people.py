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
import math
import os

import pulse.graphs
import pulse.models as db

synop = 'update information about people'
usage_extra = '[ident]'
args = pulse.utils.odict()
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only people with a matching identifier will be updated.'

def update_person (person, **kw):
    pulse.utils.log ('Creating commit graph for %s' % person.ident)
    now = datetime.datetime.now()
    threshhold = now - datetime.timedelta(days=168)
    stats = [0] * 24
    revs = db.Revision.select_revisions_since (person, False, threshhold)
    for rev in list(revs):
        idx = (now - rev.datetime).days
        idx = 23 - (idx // 7)
        if idx < 24: stats[idx] += 1
    score = 0;
    for i in range(len(stats)):
        score += (math.sqrt(i + 1) / 5) * stats[i]
    person.mod_score = int(score)
    person.save()
    graphdir = os.path.join (*([pulse.config.webdir, 'var', 'graph'] + person.ident.split('/')[1:]))
    if not os.path.exists (graphdir):
        os.makedirs (graphdir)
    graph = pulse.graphs.BarGraph (stats, 20)
    graph.save (os.path.join (graphdir, 'commits.png'))
    graph.save_data (os.path.join (graphdir, 'commits.imap'))


################################################################################
## main

def main (argv, options={}):
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix == None:
        people = db.Entity.objects.filter (type='Person')
    else:
        people = db.Entity.objects.filter (type='Person', ident__startswith=prefix)
    for person in people:
        update_person (person)
