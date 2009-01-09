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
    for url in mboxes:
        parsed = urlparse.urlparse (url)
        con = httplib.HTTPConnection (parsed[1])
        headers = {'Accept-encoding': 'gzip'}
        if kw.get('timestamps', True):
            dats = mlist.data.get ('archives', {}).get (url, {})
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
        tmp = pulse.utils.tmpfile()
        fd = open (tmp, 'w')
        fd.write (gzip.GzipFile (fileobj=StringIO.StringIO (res.read ())).read ())
        fd.close ()

        mbox = mailbox.PortableUnixMailbox (open(tmp, 'rb'))
        for msg in mbox:
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
                    # FIXME: don't use [1:-1], instead parse as email address
                    msgid = hdr[11:].strip()[1:-1]
                elif lower.startswith ('in-reply-to:'):
                    msgparent = hdr[12:].strip()[1:-1]
            if msgid == None:
                continue
            ident = mlist.ident + '/' + msgid
            post = db.ForumPost.objects.filter (ident=ident)
            try:
                post = post[0]
            except:
                post = db.ForumPost (ident=ident, type='ListPost')
            postdata = {'forum': mlist, 'name': msgsubject}

            if msgparent != None:
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
            person = db.Entity.get_by_email (msgfrom[1])
            if person.name.get('C') == None:
                person.update (name=msgfrom[0])
                person.save ()
            postdata['author'] = person

            msgdate = emailutils.parsedate_tz (msgdate)
            dt = datetime.datetime (*msgdate[:6])
            dt = dt + datetime.timedelta (seconds=msgdate[-1])
            postdata['datetime'] = dt

            post.update (postdata)
            post.save ()

        try:
            os.remove (tmp)
        except:
            pass
        mlist.data.setdefault ('archives', {})
        mlist.data['archives'].setdefault (url, {})
        mlist.data['archives'][url]['modified'] = res.getheader ('Last-Modified')
        mlist.data['archives'][url]['etag'] = res.getheader ('Etag')
        mlist.save()


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
