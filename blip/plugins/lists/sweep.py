# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

"""
Update information from mailing lists
"""

import datetime
import email.utils
import gzip
import HTMLParser
import mailbox
import os
import re
import StringIO
import urllib2
import urlparse

import blinq.config

import blip.db
import blip.sweep
import blip.utils

class ListsResponder (blip.sweep.SweepResponder):
    command = 'lists'
    synopsis = 'update information about mailing lists'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] lists [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--no-timestamps',
                                 dest='timestamps',
                                 action='store_false',
                                 default=True,
                                 help='do not check timestamps before processing files')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)

        cls.update_input_file (request)

        argv = request.get_tool_args ()
        lists = []
        if len(argv) == 0:
            lists = blip.db.Forum.select (blip.db.Forum.type == u'List')
        else:
            for arg in argv:
                ident = blip.utils.utf8dec (arg)
                lists += list(blip.db.Forum.select (blip.db.Forum.type == u'List',
                                                    blip.db.Forum.ident.like (ident)))
        for ml in lists:
            try:
                cls.update_list (ml, request)
                blip.db.flush ()
            except:
                blip.db.rollback ()
                raise
            else:
                blip.db.commit ()
        return response

    @classmethod
    def update_input_file (cls, request):
        infile = os.path.join (blinq.config.input_dir, 'lists.xml')
        if not os.path.exists (infile):
            return response

        with blip.db.Timestamp.stamped (blip.utils.utf8dec (infile), None) as stamp:
            stamp.check (request.get_tool_option ('timestamps'))
            stamp.log ()

            data = blip.data.Data (infile)
            for key in data.data.keys():
                datum = data.data[key]
                if datum['blip:type'] != 'list':
                    continue
                if not datum.has_key ('domain'):
                    continue
                domain = blip.utils.utf8dec (datum['domain'])
                mlid = blip.utils.utf8dec (datum['blip:id'])
                ident = u'/' + u'/'.join(['list', domain, mlid])
                ml = blip.db.Forum.get_or_create (ident, u'List')
                if datum.has_key ('name'):
                    ml.name = blip.utils.utf8dec (datum['name'])
                else:
                    ml.name = mlid
                ml.data['archive'] = datum.get('archive', None)
                ml.data['listinfo'] = datum.get('listinfo', None)
            blip.db.commit ()

    @classmethod
    def update_list (cls, ml, request):
        blip.utils.log ('Processing %s' % ml.ident)

        archive = ml.data.get ('archive')
        mboxes = []
        if archive is not None:
            links = LinkExtractor (archive).get_links ()
            for link in links:
                if link.endswith ('.txt.gz'):
                    mboxes.append (urlparse.urljoin (archive, link))

        cache = blip.db.CacheData.get_or_create (ml.ident, u'archives')
        now = datetime.datetime.utcnow ()

        if ml.data.get('listinfo') is not None:
            httpreq = urllib2.Request (ml.data.get ('listinfo'))
            if request.get_tool_option ('timestamps'):
                when = blip.utils.http_date (cache.data.get ('listinfo-datetime'))
                if when is not None:
                    httpreq.add_header ('If-Modified-Since', when)
            try:
                httpres = urllib2.urlopen (httpreq)
                blip.utils.log ('Processing URL %s' % ml.data['listinfo'])
                title = CrappyMailmanTitleExtractor (ml.ident.split('/')[-1])
                title.feed(httpres.read())
                title.close ()
                ml.desc = blip.utils.utf8dec (title.title)
                cache.data['listinfo-datetime'] = now
            except urllib2.HTTPError:
                pass

        cache.data.setdefault ('archive-datetimes', {})
        mboxes.reverse ()
        for url in mboxes:
            httpreq = urllib2.Request (url)
            httpreq.add_header ('Accept-encoding', 'gzip')
            if request.get_tool_option ('timestamps'):
                when = blip.utils.http_date (cache.data['archive-datetimes'].get(url))
                if when is not None:
                    httpreq.add_header ('If-Modified-Since', when)
            try:
                httpres = urllib2.urlopen (httpreq)
                blip.utils.log ('Processing archive %s' % url)
                tmp = blip.utils.tmpfile()
                fd = open (tmp, 'w')
                fd.write (gzip.GzipFile (fileobj=StringIO.StringIO (httpres.read ())).read ())
                fd.close ()
                cls.update_archive (ml, request, cache, tmp)
                try:
                    os.remove (tmp)
                except:
                    pass
            except urllib2.HTTPError:
                pass
            cache.data['archive-datetimes'][url] = now

        # FIXME: now create graphs and set the score

        ml.updated = datetime.datetime.utcnow ()
        blip.db.Queue.pop (ml.ident)

    @classmethod
    def update_archive (cls, ml, request, cache, archive):
        mbox = mailbox.PortableUnixMailbox (open(archive, 'rb'))
        i = -1
        for msg in mbox:
            i += 1
            msgfrom = msg.get ('From')
            msgdate = msg.get ('Date')
            msgsubject = msg.get ('Subject')
            if msgsubject is not None:
                msgsubject = msgsubject.strip()
            msgid = msg.get ('Message-id')
            msgparent = msg.get ('In-reply-to')
            if msgid is None:
                continue
            msgid = blip.utils.utf8dec (email.utils.parseaddr (msgid)[1])
            ident = ml.ident + u'/' + msgid
            post = blip.db.ForumPost.get_or_create (ident, u'ListPost')
            post.forum = ml
            post.name = blip.utils.utf8dec (msgsubject)

            if msgparent is not None:
                msgparent = blip.utils.utf8dec (email.utils.parseaddr (msgparent)[1])
                pident = ml.ident + u'/' + msgparent
                parent = blip.db.ForumPost.get_or_create (pident, u'ListPost')
                parent.forum = ml
                post.parent_ident = parent.ident

            msgfrom = email.utils.parseaddr (msgfrom)
            personident = u'/person/' + blip.utils.utf8dec (msgfrom[1])
            person = blip.db.Entity.get_or_create (personident, u'Person')
            person.extend (name=msgfrom[0])
            post.author_ident = person.ident
            if person.ident != personident:
                post.person_alias_ident = personident
            blip.db.Queue.push (person.ident)

            msgdate = email.utils.parsedate_tz (msgdate)
            try:
                dt = datetime.datetime (*msgdate[:6])
                if msgdate[-1] is not None:
                    dt = dt + datetime.timedelta (seconds=msgdate[-1])
            except:
                dt = None
            # Sometimes the date is screwed up. If the reported date is before
            # the beginning of time, try to use a date from the Recieved header.
            if dt is None or dt < datetime.datetime(1970, 1, 1):
                dt = None
                received = msg.get ('Received')
                received = re.sub ('\(.*', '', received.split(';')[-1]).strip()
                received = email.utils.parsedate_tz (received)
                try:
                    dt = datetime.datetime (*received[:6])
                    if received[-1] is not None:
                        dt = dt + datetime.timedelta (seconds=received[-1])
                except:
                    pass
            post.datetime = dt
            post.weeknum = blip.utils.weeknum (dt)

            # FIXME
            #post.web = urlbase + 'msg%05i.html' % i


class LinkExtractor (HTMLParser.HTMLParser):
    def __init__ (self, url):
        self._links = []
        HTMLParser.HTMLParser.__init__ (self)
        for line in urllib2.urlopen (url):
            self.feed (line)
        self.close ()

    def handle_starttag (self, tag, attrs):
        if tag == 'a':
            for att, val in attrs:
                if att == 'href':
                    self._links.append (val)

    def get_links (self):
        return self._links

class CrappyMailmanTitleExtractor (HTMLParser.HTMLParser):
    def __init__ (self, listname):
        self._listname = listname
        self.title = None
        HTMLParser.HTMLParser.__init__ (self)

    def handle_data (self, data):
        data = re.sub ('[\n\s]+', ' ', data).strip ()
        if data.startswith (self._listname + ' -- '):
            self.title = data[len(self._listname) + 4:]