# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
# Suite 330, Boston, MA  0211-1307  USA.
#

import datetime
import os

import blinq.ext

import blip.data
import blip.db
import blip.graphs
import blip.sweep
import blip.utils

import blip.plugins.queue.sweep

class EntityHandler (blinq.ext.ExtensionPoint):
    @classmethod
    def handle_entity (cls, entity, request):
        pass

class PeopleResponder (blip.sweep.SweepResponder,
                       blip.plugins.queue.sweep.QueueHandler):
    command = 'people'
    synopsis = 'update information about people'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] people [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--no-timestamps',
                                 dest='timestamps',
                                 action='store_false',
                                 default=True,
                                 help='do not check timestamps before processing files')
        request.add_tool_option ('--until',
                                 dest='until',
                                 metavar='SECONDS',
                                 help='only process modules older than SECONDS seconds')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)
        argv = request.get_tool_args ()

        dbargs = []
        until = request.get_tool_option ('until')
        if until is not None:
            sep = until.rfind (':')
            tlhour = tlmin = tlsec = 0
            if sep >= 0:
                tlsec = int(until[sep+1:])
                tlpre = until[:sep]
                sep = tlpre.rfind (':')
                if sep >= 0:
                    tlmin = int(tlpre[sep+1:])
                    tlhour = int(tlpre[:sep])
                else:
                    tlmin = int(tlpre)
            else:
                tlsec = int(until)
            until = 3600 * tlhour + 60 * tlmin + tlsec
            then = datetime.datetime.utcnow() - datetime.timedelta(seconds=int(until))
            dbargs.append (blip.db.Entity.updated < then)

        entities = []
        if len(argv) == 0:
            entities = list(blip.db.Entity.select (blip.db.Entity.type == u'Person', *dbargs))
        else:
            for arg in argv:
                ident = blip.utils.utf8dec (arg)
                entities += list(blip.db.Entity.select (blip.db.Entity.type == u'Person',
                                                        blip.db.Entity.ident.like (ident),
                                                        *dbargs))

        entities = blinq.utils.attrsorted (entities, 'updated')
        for entity in entities:
            try:
                cls.update_person (entity, request)
                blip.db.flush ()
            except:
                blip.db.rollback ()
                raise
            else:
                blip.db.commit ()
        return response

    @classmethod
    def update_person (cls, entity, request):
        blip.utils.log ('Processing %s' % entity.ident)
        for handler in EntityHandler.get_extensions ():
            handler.handle_entity (entity, request)

        cls.update_commit_graphs (entity, request)

        entity.updated = datetime.datetime.utcnow ()
        blip.db.Queue.pop (entity.ident)

    @staticmethod
    def update_commit_graphs (entity, request):
        now = datetime.datetime.utcnow ()
        thisweek = blip.utils.weeknum ()
        numweeks = 104
        i = 0
        finalrev = blip.db.Revision.select_revisions (person=entity)
        finalrev = finalrev.order_by ('datetime')
        outpath = None
        try:
            finalrev = finalrev[0].ident
            stillrev = True
        except IndexError:
            finalrev = None
            stillrev = False
        while stillrev or i < 2:
            topweek = thisweek - (i * numweeks)
            revstot = blip.db.Revision.count_revisions (person=entity)
            revs = blip.db.Revision.select_revisions (week_range=((topweek - numweeks + 1), topweek),
                                                      person=entity)
            if stillrev:
                fname = u'commits-' + str(i) + '.png'
                of = blip.db.OutputFile.select_one (type=u'graphs', ident=entity.ident, filename=fname)
                if i == 0 and of is not None:
                    if request.get_tool_option ('timestamps', True):
                        revcount = of.data.get ('revcount', 0)
                        weeknum = of.data.get ('weeknum', None)
                        if weeknum == thisweek:
                            rev = None
                            if revcount == revstot:
                                return
                elif of is None:
                    of = blip.db.OutputFile (type=u'graphs', ident=entity.ident,
                                             filename=fname, datetime=now)
                outpath = of.get_file_path ()
            else:
                of = None

            if i == 0:
                blip.utils.log ('Creating commit graphs for %s' % entity.ident)

            stats = [0] * numweeks
            revs = list(revs)
            for rev in revs:
                if rev.ident == finalrev:
                    stillrev = False
                idx = rev.weeknum - topweek + numweeks - 1
                stats[idx] += 1

            if i == 0:
                scorestats = stats[numweeks - 26:]
                score = blip.utils.score (scorestats)
                entity.score = score

                scorestats = scorestats[:-3]
                avg = int(round(sum(scorestats) / (len(scorestats) * 1.0)))
                scorestats = scorestats + [avg, avg, avg]
                old = blip.utils.score (scorestats)
                score_diff = score - old
                entity.score_diff = score_diff

            if of is not None:
                graph = blip.graphs.BarGraph (stats, 80, height=40)
                graph.save (of.get_file_path ())

            if i == 0:
                stats0 = stats
            elif i == 1 and outpath is not None:
                graph_t = blip.graphs.BarGraph (stats + stats0, 80, height=40, tight=True)
                graph_t.save (os.path.join (os.path.dirname (outpath), 'commits-tight.png'))

            if of is not None:
                of.data['coords'] = zip (graph.get_coords(), stats,
                                         range(topweek - numweeks + 1, topweek + 1))
                if len(revs) > 0:
                    of.data['revcount'] = revstot
                of.data['weeknum'] = topweek

            i += 1

    @classmethod
    def process_queued (cls, ident, request):
        if ident.startswith (u'/person/'):
            ent = blip.db.Entity.select_one (ident=ident)
            if ent is not None:
                cls.update_person (ent, request)


class TeamsResponder (blip.sweep.SweepResponder,
                      blip.plugins.queue.sweep.QueueHandler):
    command = 'teams'
    synopsis = 'update information about teams'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] teams [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--no-timestamps',
                                 dest='timestamps',
                                 action='store_false',
                                 default=True,
                                 help='do not check timestamps before processing files')
        request.add_tool_option ('--until',
                                 dest='until',
                                 metavar='SECONDS',
                                 help='only process modules older than SECONDS seconds')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)

        cls.update_input_file (request)

        dbargs = []
        until = request.get_tool_option ('until')
        if until is not None:
            sep = until.rfind (':')
            tlhour = tlmin = tlsec = 0
            if sep >= 0:
                tlsec = int(until[sep+1:])
                tlpre = until[:sep]
                sep = tlpre.rfind (':')
                if sep >= 0:
                    tlmin = int(tlpre[sep+1:])
                    tlhour = int(tlpre[:sep])
                else:
                    tlmin = int(tlpre)
            else:
                tlsec = int(until)
            until = 3600 * tlhour + 60 * tlmin + tlsec
            then = datetime.datetime.utcnow() - datetime.timedelta(seconds=int(until))
            dbargs.append (blip.db.Entity.updated < then)

        argv = request.get_tool_args ()
        entities = []
        if len(argv) == 0:
            entities = list(blip.db.Entity.select (blip.db.Entity.type == u'Team', *dbargs))
        else:
            for arg in argv:
                ident = blip.utils.utf8dec (arg)
                entities += list(blip.db.Entity.select (blip.db.Entity.type == u'Team',
                                                        blip.db.Entity.ident.like (ident),
                                                        *dbargs))
        entities = blinq.utils.attrsorted (entities, 'updated')
        for entity in entities:
            try:
                cls.update_team (entity, request)
                blip.db.flush ()
            except:
                blip.db.rollback ()
                raise
            else:
                blip.db.commit ()
        return response

    @classmethod
    def update_input_file (cls, request):
        infile = os.path.join (blinq.config.input_dir, 'teams.xml')
        if not os.path.exists (infile):
            return response

        with blip.db.Timestamp.stamped (blip.utils.utf8dec (infile), None) as stamp:
            stamp.check (request.get_tool_option ('timestamps'))
            stamp.log ()

            def process_team_datum (datum):
                ident = u'/team/' + blip.utils.utf8dec (datum['blip:id'])
                team = blip.db.Entity.get_or_create (ident, u'Team')
                if datum.has_key ('name'):
                    team.name = blip.utils.utf8dec (datum['name'])

                members = []
                for person in datum.get ('coordinator', []):
                    ent = blip.db.Entity.get_or_create (blip.utils.utf8dec (person),
                                                        u'Person')
                    rel = blip.db.TeamMember.set_related (team, ent)
                    rel.coordinator = True
                    members.append (rel)
                team.set_relations (blip.db.TeamMember, members)

                subteams = []
                for subteam in datum.get ('team', {}).values ():
                    ent = process_team_datum (subteam)
                    ent.parent = team
                    subteams.append (ent)
                team.set_children (u'Team', subteams)

                for alias in datum.get ('alias', []):
                    blip.db.Alias.update_alias (team, blip.utils.utf8dec (alias))

                return team

            data = blip.data.Data (infile)
            for key in data.data.keys():
                datum = data.data[key]
                if datum['blip:type'] == 'team':
                    process_team_datum (datum)

    @classmethod
    def update_team (cls, entity, request):
        blip.utils.log ('Processing %s' % entity.ident)
        for handler in EntityHandler.get_extensions ():
            handler.handle_entity (entity, request)

        entity.updated = datetime.datetime.utcnow ()
        blip.db.Queue.pop (entity.ident)

    @classmethod
    def process_queued (cls, ident, request):
        if ident.startswith (u'/team/'):
            ent = blip.db.Entity.select_one (ident=ident)
            if ent is not None:
                cls.update_team (ent, request)

# FIXME: move to new blogs plugin
if False:
    feed = person.data.get ('blog')
    if feed != None:
        bident = '/blog' + person.ident
        forum = pulse.db.Forum.get_or_create (bident, u'Blog')
        forum.data['feed'] = feed
        etag = forum.data.get ('etag')
        modified = forum.data.get ('modified')
        feed = pulse.feedparser.parse (feed, etag=etag, modified=modified)
        if feed.status == 200:
            pulse.utils.log ('Processing blog %s' % bident)
            for entry in feed['entries']:
                postid = entry.get ('id', entry.link)
                eident = bident + '/' + postid
                if pulse.db.ForumPost.select (ident=eident, type=u'BlogPost').count () == 0:
                    post = pulse.db.ForumPost (ident=eident, type=u'BlogPost')
                    postdata = {
                        'forum' : forum,
                        'author' : person,
                        'name' : entry.title,
                        'web' : entry.link
                        }
                    if entry.has_key ('date_parsed'):
                        postdata['datetime'] = datetime.datetime (*entry.date_parsed[:6])
                    post.update (postdata)
            forum.data['etag'] = feed.get('etag')
            forum.data['modified'] = feed.get('modified')
