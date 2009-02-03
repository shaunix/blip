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
import Image
import os
import urllib

import pulse.feedparser
import pulse.graphs
import pulse.models as db
import pulse.pulsate
import pulse.xmldata

synop = 'update information about people and teams'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only people and teams with a matching identifier will be updated.'


def update_person (person, **kw):
    now = datetime.datetime.now()
    thisweek = pulse.utils.weeknum (datetime.datetime.utcnow())
    of = db.OutputFile.objects.filter (type='graphs', ident=person.ident, filename='commits.png')
    try:
        of = of[0]
    except IndexError:
        of = None

    pulse.pulsate.update_graphs (person, {'person' : person}, 80, **kw)

    feed = person.data.get ('blog')
    if feed != None:
        bident = '/blog' + person.ident
        forum = db.Forum.get_record (bident, 'Blog')
        forum.data['feed'] = feed
        etag = forum.data.get ('etag')
        modified = forum.data.get ('modified')
        feed = pulse.feedparser.parse (feed, etag=etag, modified=modified)
        if feed.status == 200:
            pulse.utils.log ('Processing blog %s' % bident)
            for entry in feed['entries']:
                postid = entry.get ('id', entry.link)
                eident = bident + '/' + postid
                if db.ForumPost.objects.filter (ident=eident, type='BlogPost').count () == 0:
                    post = db.ForumPost (ident=eident, type='BlogPost')
                    postdata = {
                        'forum' : forum,
                        'author' : person,
                        'name' : entry.title,
                        'web' : entry.link
                        }
                    if entry.has_key ('date_parsed'):
                        postdata['datetime'] = datetime.datetime (*entry.date_parsed[:6])
                    post.update (postdata)
                    post.save ()
            forum.data['etag'] = feed.get('etag')
            forum.data['modified'] = feed.get('modified')
            forum.save()
        else:
            pulse.utils.log ('Skipping blog %s' % bident)

    db.Queue.remove ('people', person.ident)
    person.save()


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
