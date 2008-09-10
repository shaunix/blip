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

synop = 'update information about people'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only people with a matching identifier will be updated.'


def update_people (**kw):
    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'people.xml'))
    icondir = os.path.join (pulse.config.web_icons_dir, 'people')
    for key in data.keys():
        if not data[key]['__type__'] == 'person':
            continue
        if not data[key].has_key ('id'):
            continue
        ident = '/person/' + data[key]['id']
        person = db.Entity.get_record (ident, 'Person')
        aliases = data[key].get ('alias', [])
        needs_update = False
        for alias in aliases:
            try:
                aliasrec = db.Alias.objects.filter (ident=alias)
                aliasrec = aliasrec[0]
            except IndexError:
                needs_update = True
                aliasrec = db.Alias (ident=alias)
            aliasrec.entity = person
            aliasrec.save()
            try:
                rec = db.Entity.objects.filter (ident=alias, type='Person')
                rec = rec[0]
            except IndexError:
                rec = None
            if rec != None:
                pulse.utils.log ('Copying %s to %s' % (alias, ident))
                pdata = {}
                for pkey, pval in rec.data.items():
                    pdata[pkey] = pval
                pdata['name'] = rec.name
                pdata['desc'] = rec.desc
                pdata['icon_dir'] = rec.icon_dir
                pdata['icon_name'] = rec.icon_name
                pdata['email'] = rec.email
                pdata['web'] = rec.web
                pdata['nick'] = rec.nick
                pdata['mod_score'] = rec.mod_score
                
                rels = db.DocumentEntity.objects.filter (pred=rec)
                for rel in rels:
                    needs_update = True
                    rel.pred = person
                    rel.save()
                rels = db.ModuleEntity.objects.filter (pred=rec)
                for rel in rels:
                    needs_update = True
                    rel.pred = person
                    rel.save()
                branches = db.Branch.objects.filter (mod_person=rec)
                for branch in branches:
                    needs_update = True
                    branch.mod_person = person
                    branch.save()
                revs = db.Revision.objects.filter (person=rec)
                for rev in revs:
                    needs_update = True
                    rev.person = person
                    rev.alias = alias
                    rev.save()
                rec.delete()

        for k in ('name', 'nick', 'email', 'web', 'blog'):
            if data[key].has_key (k):
                person.update(**{k : data[key][k]})
        if data[key].has_key ('icon'):
            # FIXME: we really shouldn't redownload these every time,
            # but we want to make sure we get updates versions.  Check
            # into using timestamps and If-Modified-Since
            iconhref = data[key]['icon']
            iconname = urllib.quote ('/'.join (ident.split('/')[2:]), '')
            iconorig = os.path.join (icondir, iconname + '@@original.png')
            if not os.path.isdir (icondir):
                os.makedirs (icondir)
            urllib.urlretrieve (iconhref, iconorig)
            im = Image.open (iconorig)
            im.thumbnail((36, 36), Image.ANTIALIAS)
            im.save (os.path.join (icondir, iconname + '.png'), 'PNG')
            person.update ({'icon_dir' : 'people', 'icon_name' : iconname})

        if needs_update:
            update_person (person, **kw)
        else:
            person.save()


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

    person.save()


################################################################################
## main

def main (argv, options={}):
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    update_people (timestamps=timestamps)

    if prefix == None:
        people = db.Entity.objects.filter (type='Person')
    else:
        people = db.Entity.objects.filter (type='Person', ident__startswith=prefix)
    for person in people:
        update_person (person, timestamps=timestamps)
