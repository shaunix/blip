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
import urllib

import vobject

import pulse.db
import pulse.feedparser
import pulse.graphs
import pulse.utils

def update_graphs (record, select, max, **kw):
    now = datetime.datetime.utcnow ()
    thisweek = pulse.utils.weeknum ()
    numweeks = kw.get('numweeks', 104)
    i = 0
    finalrev = pulse.db.Revision.select_revisions (**select).order_by ('datetime')
    outpath = None
    try:
        finalrev = finalrev[0].id
        stillrev = True
    except IndexError:
        finalrev = None
        stillrev = False
    while stillrev or i < 2:
        topweek = thisweek - (i * numweeks)
        revstot = pulse.db.Revision.count_revisions (**select)
        revs = pulse.db.Revision.select_revisions (week_range = ((topweek - numweeks + 1), topweek),
                                                   **select)

        if stillrev:
            fname = u'commits-' + str(i) + '.png'
            of = pulse.db.OutputFile.select (type=u'graphs', ident=record.ident, filename=fname)
            try:
                of = of[0]
            except IndexError:
                of = None
            if i == 0 and of != None:
                if kw.get('timestamps', True):
                    revcount = of.data.get ('revcount', 0)
                    weeknum = of.data.get ('weeknum', None)
                    if weeknum == thisweek:
                        rev = None
                        if revcount == revstot:
                            pulse.utils.log ('Skipping commit graph for %s' % record.ident)
                            return
            elif of == None:
                of = pulse.db.OutputFile (type=u'graphs', ident=record.ident,
                                          filename=fname, datetime=now)
            outpath = of.get_file_path()
        else:
            of = None

        if i == 0:
            pulse.utils.log ('Creating commit graphs for %s' % record.ident)

        stats = [0] * numweeks
        revs = list(revs)
        for rev in revs:
            if rev.id == finalrev:
                stillrev = False
            idx = rev.weeknum - topweek + numweeks - 1
            stats[idx] += 1

        if i == 0:
            scorestats = stats[numweeks - 26:]
            score = pulse.utils.score (scorestats)
            record.mod_score = score
            scorestats = scorestats[:-3]
            avg = int(round(sum(scorestats) / (len(scorestats) * 1.0)))
            scorestats = scorestats + [avg, avg, avg]
            old = pulse.utils.score (scorestats)
            record.mod_score_diff = score - old

        if of != None:
            graph = pulse.graphs.BarGraph (stats, max, height=40)
            graph.save (of.get_file_path())

        if i == 0:
            stats0 = stats
        elif i == 1 and outpath != None:
            graph_t = pulse.graphs.BarGraph (stats + stats0, max, height=40, tight=True)
            graph_t.save (os.path.join (os.path.dirname (outpath), 'commits-tight.png'))

        if of != None:
            of.data['coords'] = zip (graph.get_coords(), stats, range(topweek - numweeks + 1, topweek + 1))
            if len(revs) > 0:
                of.data['revcount'] = revstot
            of.data['weeknum'] = topweek

        i += 1


def update_links (record, sources, **kw):
    links = []
    for source in sources:
        linksources = record.data.get ('linksources', {})
        linksources.setdefault (source, {})
        etag = linksources[source].get ('etag')
        modified = linksources[source].get ('modified')
        feed = pulse.feedparser.parse (source, etag=etag, modified=modified)
        if feed.status == 200:
            pulse.utils.log ('Processing links at %s' % source)
            for entry in feed['entries']:
                if not entry.has_key ('link'):
                    continue
                if entry.has_key ('updated_parsed'):
                    updated = datetime.datetime (*entry.updated_parsed[:6])
                else:
                    updated = None
                links.append ((entry.link,
                               entry.get ('title', entry.link),
                               entry.get ('description'),
                               updated,
                               source))
            linksources[source]['etag'] = feed.get('etag')
            linksources[source]['modified'] = feed.get('modified')
        else:
            # Not at all optimal, but not causing significant slowdowns
            # with any data we're actually seeing
            for link in record.data.get ('links', []):
                if link[4] == source:
                    links.append (link)
    record.update(data={'linksources': linksources,
                        'links': sorted (links, cmp=lambda x, y: cmp (x[3], y[3]))
                        })


def update_schedule (record, url, **kw):
    pulse.utils.log ('Processing schedule at %s' % url)
    cal = vobject.readOne (urllib.urlopen (url))
    schedule = []
    for event in cal.getChildren ():
        if event.name != 'VEVENT':
            continue
        schedule.append ((event.dtstart.value, event.dtend.value,
                          event.summary.value, event.description.value))
    record.update(data={'schedule': sorted (schedule, cmp=lambda x, y: cmp (x[0], y[0]))})

__all__ = ['docs','i18n','icons','init','modules','people','queue','sets']
