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
args['shallow'] = (None, 'only update information from the XML input file')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only people and teams with a matching identifier will be updated.'


def update_entities (**kw):
    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'people.xml'))
    for key in data.keys():
        if not data[key]['__type__'] in ('person', 'team'):
            continue
        if not data[key].has_key ('id'):
            continue
        type = {'person':'Person', 'team':'Team'}[data[key]['__type__']]
        ident = '/' + data[key]['__type__'] + '/' + data[key]['id']
        entity = db.Entity.get_record (ident, type)
        aliases = data[key].get ('alias', [])
        needs_update = False

        for alias in aliases:
            needs_update = update_alias (entity, alias, **kw) or needs_update

        parent = data[key].get ('parent', None)
        if parent != None:
            entity.parent = db.Entity.get_record (parent, 'Team')

        coords = data[key].get ('coordinators', [])
        if isinstance (coords, list) and len(coords) > 0:
            rels = []
            for coord in coords:
                rec = db.Entity.get_record (coord, 'Person')
                rel = db.TeamMember.set_related (entity, rec, coordinator=True)
                rels.append (rel)
            entity.set_relations (db.TeamMember, rels)
        else:
            entity.set_relations (db.TeamMember, [])

        for k in ('name', 'nick', 'email', 'web', 'blog'):
            if data[key].has_key (k):
                entity.update(**{k : data[key][k]})
        if data[key].has_key ('icon'):
            # FIXME: we really shouldn't redownload these every time,
            # but we want to make sure we get updates versions.  Check
            # into using timestamps and If-Modified-Since
            iconhref = data[key]['icon']
            iconname = urllib.quote ('/'.join (ident.split('/')[2:]), '')

            icondir = {'person':'people', 'team':'teams'}[data[key]['__type__']]
            iconpath = os.path.join (pulse.config.web_icons_dir, icondir)
            iconorig = os.path.join (iconpath, iconname + '@@original.png')
            if not os.path.isdir (iconpath):
                os.makedirs (iconpath)
            urllib.urlretrieve (iconhref, iconorig)
            im = Image.open (iconorig)
            im.thumbnail((36, 36), Image.ANTIALIAS)
            im.save (os.path.join (iconpath, iconname + '.png'), 'PNG')
            entity.update ({'icon_dir' : icondir, 'icon_name' : iconname})

        if needs_update:
            update_entity (entity, **kw)
        else:
            entity.save()


def update_alias (entity, alias, **kw):
    needs_update = False
    try:
        aliasrec = db.Alias.objects.filter (ident=alias)
        aliasrec = aliasrec[0]
    except IndexError:
        needs_update = True
        aliasrec = db.Alias (ident=alias)
    aliasrec.entity = entity
    aliasrec.save()
    try:
        rec = db.Entity.objects.filter (ident=alias, type=entity.type)
        rec = rec[0]
    except IndexError:
        rec = None
    if rec == None:
        return needs_update

    pulse.utils.log ('Copying %s to %s' % (alias, entity.ident))
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
        rel.pred = entity
        rel.save()
    rels = db.ModuleEntity.objects.filter (pred=rec)
    for rel in rels:
        needs_update = True
        rel.pred = entity
        rel.save()
    rels = db.TeamMember.objects.filter (subj=rec)
    for rel in rels:
        needs_update = True
        rel.subj = entity
        rel.save()
    rels = db.TeamMember.objects.filter (pred=rec)
    for rel in rels:
        needs_update = True
        rel.pred = entity
        rel.save()
    branches = db.Branch.objects.filter (mod_person=rec)
    for branch in branches:
        needs_update = True
        branch.mod_person = entity
        branch.save()
    revs = db.Revision.objects.filter (person=rec)
    for rev in revs:
        needs_update = True
        rev.person = entity
        rev.alias = alias
        rev.save()
    rec.delete()

    return needs_update


def update_entity (entity, **kw):
    now = datetime.datetime.now()
    thisweek = pulse.utils.weeknum (datetime.datetime.utcnow())
    of = db.OutputFile.objects.filter (type='graphs', ident=entity.ident, filename='commits.png')
    try:
        of = of[0]
    except IndexError:
        of = None

    pulse.pulsate.update_graphs (entity, {'person' : entity}, 80, **kw)

    feed = entity.data.get ('blog')
    if feed != None:
        bident = '/blog' + entity.ident
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
                        'author' : entity,
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

    db.Queue.remove ('people', entity.ident)
    entity.save()


################################################################################
## main

def main (argv, options={}):
    shallow = options.get ('--shallow', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    update_entities (timestamps=timestamps, shallow=shallow)

    if not shallow:
        if prefix == None:
            entities = db.Entity.objects.filter (type__in=('Person', 'Team'))
        else:
            entities = db.Entity.objects.filter (type__in=('Person', 'Team'), ident__startswith=prefix)
        for entity in entities:
            update_entity (entity, timestamps=timestamps, shallow=shallow)
