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
import email
try:
    import email.Utils as emailutils
except:
    import email.utils as emailutils
import gzip
import HTMLParser
import httplib
import mailbox
import os
import urllib
import urlparse
import StringIO

import pulse.models as db
import pulse.utils
import pulse.xmldata

synop = 'update information about mailing lists'
args = pulse.utils.odict()
args['shallow'] = (None, 'only update information from the XML input file')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')

def update_lists (**kw):
    queue = []
    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'lists.xml'))

    for key in data.keys():
        if not data[key]['__type__'] == 'list':
            continue
        if not (data[key].has_key ('id') and data[key].has_key ('ident')):
            continue
        mlist = db.Forum.get_record (data[key]['ident'], 'List')

        for k in ('name', 'email', 'list_id', 'list_info', 'list_archive'):
            if data[key].has_key (k):
                mlist.update(**{k : data[key][k]})

        mlist.save()

    return queue


class LinkExtractor (HTMLParser.HTMLParser):
    def __init__ (self, url):
        self._links = []
        HTMLParser.HTMLParser.__init__ (self)
        for line in urllib.urlopen (url):
            self.feed (line)
        self.close ()

    def handle_starttag (self, tag, attrs):
        if tag == 'a':
            for att, val in attrs:
                if att == 'href':
                    self._links.append (val)

    def get_links (self):
        return self._links


def update_list (mlist, **kw):
    archive = mlist.data.get ('list_archive')
    mboxes = []
    if archive != None:
        links = LinkExtractor (archive).get_links ()
        for link in links:
            if link.endswith ('.txt.gz'):
                mboxes.append (urlparse.urljoin (archive, link))
    mlist.data.setdefault ('archives', {})
    for url in mboxes:
        parsed = urlparse.urlparse (url)
        con = httplib.HTTPConnection (parsed[1])
        headers = {'Accept-encoding': 'gzip'}
        if kw.get('timestamps', True):
            dats = mlist.data['archives'].get (url, {})
            mod = dats.get ('modified')
            if mod != None:
                headers['If-Modified-Since'] = mod
            etag = dats.get ('etag')
            if etag != None:
                headers['Etag'] =etag
        con.request ('GET', parsed[2], None, headers)
        res = con.getresponse ()
        if res.status != 200:
            continue
        urlfile = url
        urlslash = urlfile.rfind ('/')
        if urlslash >= 0:
            urlfile = urlfile[urlslash+1:]
        pulse.utils.log ('Processing list archive %s %s' % (mlist.ident, urlfile))
        urlbase = url[:-7] + '/'
        tmp = pulse.utils.tmpfile()
        fd = open (tmp, 'w')
        fd.write (gzip.GzipFile (fileobj=StringIO.StringIO (res.read ())).read ())
        fd.close ()

        mbox = mailbox.PortableUnixMailbox (open(tmp, 'rb'))
        i = -1
        for msg in mbox:
            i += 1
            msgfrom = msgdate = msgsubject = msgid = msgparent = None
            for hdr in msg.headers:
                lower = hdr.lower()
                if lower.startswith ('from:'):
                    msgfrom = hdr[5:]
                elif lower.startswith ('date:'):
                    msgdate = hdr[5:]
                elif lower.startswith ('subject:'):
                    msgsubject = hdr[8:].strip()
                elif lower.startswith ('message-id:'):
                    msgid = hdr[11:]
                elif lower.startswith ('in-reply-to:'):
                    msgparent = hdr[12:]
            if msgid == None:
                continue
            msgid = pulse.utils.utf8dec (emailutils.parseaddr (msgid)[1])
            ident = mlist.ident + '/' + msgid
            post = db.ForumPost.objects.filter (ident=ident)
            try:
                post = post[0]
            except:
                post = db.ForumPost (ident=ident, type='ListPost')
            postdata = {'forum': mlist, 'name': msgsubject}

            if msgparent != None:
                msgparent = pulse.utils.utf8dec (emailutils.parseaddr (msgparent)[1])
                pident = mlist.ident + '/' + msgparent
                parent = db.ForumPost.objects.filter (ident=pident)
                try:
                    parent = parent[0]
                except:
                    parent = db.ForumPost (ident=pident, type='ListPost')
                parent.forum = mlist
                parent.save ()
                postdata['parent'] = parent

            msgfrom = emailutils.parseaddr (msgfrom)
            person = db.Entity.get_by_email (pulse.utils.utf8dec (msgfrom[1]))
            if person.name.get('C') == None:
                person.update (name=msgfrom[0])
                person.save ()
            postdata['author'] = person
            db.Queue.push ('people', person.ident)

            msgdate = emailutils.parsedate_tz (msgdate)
            try:
                dt = datetime.datetime (*msgdate[:6])
                if msgdate[-1] != None:
                    dt = dt + datetime.timedelta (seconds=msgdate[-1])
            except:
                dt = None
            postdata['datetime'] = dt

            postdata['web'] = urlbase + 'msg%05i.html' % i

            post.update (postdata)
            post.save ()

        try:
            os.remove (tmp)
        except:
            pass
        mlist.data['archives'].setdefault (url, {})
        mlist.data['archives'][url]['modified'] = res.getheader ('Last-Modified')
        mlist.data['archives'][url]['etag'] = res.getheader ('Etag')

    update_graphs (mlist, 100, **kw)
    mlist.save()


def update_graphs (mlist, max, **kw):
    now = datetime.datetime.now ()
    thisweek = pulse.utils.weeknum ()
    numweeks = 104
    i = 0
    finalpost = db.ForumPost.objects.filter (forum=mlist, datetime__isnull=False, weeknum__gt=0).order_by ('datetime')
    outpath = None
    try:
        finalpost = finalpost[0].id
        stillpost = True
    except:
        finalpost = None
        stillpost = False
    while stillpost or i < 2:
        topweek = thisweek - (i * numweeks)
        if topweek < 0:
            break
        posts = db.ForumPost.objects.filter (forum=mlist,
                                             weeknum__gt=(topweek - numweeks),
                                             weeknum__lte=topweek)
        postcount = posts.count()
        if stillpost:
            fname = 'posts-' + str(i) + '.png'
            of = db.OutputFile.objects.filter (type='graphs', ident=mlist.ident, filename=fname)
            try:
                of = of[0]
            except IndexError:
                of = None
            if i == 0 and of != None:
                if kw.get('timestamps', True):
                    count = of.data.get ('count', None)
                    weeknum = of.data.get ('weeknum', None)
                    if weeknum == thisweek and postcount == count:
                        pulse.utils.log ('Skipping activity graph for %s' % mlist.ident)
                        return
            elif of == None:
                of = db.OutputFile (type='graphs', ident=mlist.ident, filename=fname, datetime=now)
            outpath = of.get_file_path()
        else:
            of = None

        if i == 0:
            pulse.utils.log ('Creating activity graphs for %s' % mlist.ident)

        stats = [0] * numweeks
        posts = list (posts)
        for post in posts:
            if post.id == finalpost:
                stillpost = False
            idx = post.weeknum - topweek + numweeks - 1
            stats[idx] += 1

        if i == 0:
            score = pulse.utils.score (stats[numweeks - 26:])
            mlist.post_score = score

        if of != None:
            graph = pulse.graphs.BarGraph (stats, max, height=40)
            graph.save (of.get_file_path())

        if i == 0:
            stats0 = stats
        elif i == 1 and outpath != None:
            graph_t = pulse.graphs.BarGraph (stats + stats0, max, height=40, tight=True)
            graph_t.save (os.path.join (os.path.dirname (outpath), 'posts-tight.png'))

        if of != None:
            of.data['coords'] = zip (graph.get_coords(), stats, range(topweek - numweeks + 1, topweek + 1))
            of.data['count'] = postcount
            of.data['weeknum'] = topweek
            of.save()

        i += 1


def main (argv, options={}):
    shallow = options.get ('--shallow', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    queue = update_lists (timestamps=timestamps, shallow=shallow)

    if not shallow:
        for mlist in queue:
            update_list (mlist, timestamps=timestamps, shallow=shallow)
        if prefix == None:
            mlists = db.Forum.objects.filter (type='List')
        else:
            mlists = db.Forum.objects.filter (type='List', ident__startswith=prefix)
        for mlist in mlists:
            update_list (mlist, timestamps=timestamps, shallow=shallow)
    else:
        for mlist in queue:
            db.Queue.push ('lists', mlist.ident)
