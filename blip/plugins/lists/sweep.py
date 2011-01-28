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
import RDF
import re
import StringIO
import urllib2
import urlparse

import blinq.config

import blip.db
import blip.sweep
import blip.utils

import blip.plugins.doap.sweep
import blip.plugins.scores.sweep

from blip.plugins.lists.utils import *

class ListsResponder (blip.sweep.SweepResponder,
                      blip.plugins.scores.sweep.ScoreUpdater):
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
            return

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
            try:
                links = LinkExtractor (archive).get_links ()
                for link in links:
                    if link.endswith ('.txt.gz') or link.endswith ('.txt'):
                        mboxes.append (urlparse.urljoin (archive, link))
            except:
                pass

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
                httpres.close ()
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
                if url.endswith ('.txt.gz'):
                    fd.write (gzip.GzipFile (fileobj=StringIO.StringIO (httpres.read ())).read ())
                else:
                    fd.write (httpres.read())
                fd.close ()
                httpres.close ()
                cls.update_archive (ml, request, cache, tmp)
                try:
                    os.remove (tmp)
                except:
                    pass
            except urllib2.HTTPError:
                pass
            cache.data['archive-datetimes'][url] = now

        cls.update_score (ml)

        ml.updated = datetime.datetime.utcnow ()
        blip.db.Queue.pop (ml.ident)

    @classmethod
    def update_score (cls, ml):
        store = blip.db.get_store (blip.db.ForumPost)
        thisweek = blip.utils.weeknum()
        sel = store.find ((blip.db.ForumPost.weeknum, blip.db.Count('*')),
                          blip.db.And (blip.db.ForumPost.forum == ml,
                                       blip.db.ForumPost.weeknum > thisweek - 26,
                                       blip.db.ForumPost.weeknum <= thisweek))
        sel = sel.group_by (blip.db.ForumPost.weeknum)
        sel = sel.order_by (blip.db.Desc (blip.db.ForumPost.weeknum))
        stats = [0 for i in range(26)]
        for week, cnt in list(sel):
            stats[week - (thisweek - 25)] = cnt
        ml.score = blip.utils.score (stats)

        stats = stats[:-3]
        avg = int(round(sum(stats) / (len(stats) * 1.0)))
        stats = stats + [avg, avg, avg]
        old = blip.utils.score (stats)
        ml.score_diff = ml.score - old

    @classmethod
    def update_scores (cls, request, ident):
        if ident is not None:
            mls = list(blip.db.Forum.select (blip.db.Forum.type == u'List',
                                             blip.db.Forum.ident.like (ident),
                                             blip.db.Forum.score > 0))
        else:
            mls = list(blip.db.Forum.select (blip.db.Forum.type == u'List',
                                             blip.db.Forum.score > 0))
        for ml in mls:
            blip.utils.log ('Updating score for ' + ml.ident)
            cls.update_score (ml)

    @classmethod
    def update_archive (cls, ml, request, cache, archive):
        mbox = mailbox.mbox (archive)
        # Any date outside this range is probably crap
        clamp = (datetime.datetime(1970, 1, 1),
                 datetime.datetime.utcnow() + datetime.timedelta (seconds=86400))
        outdir = os.path.join (*([blinq.config.web_files_dir] + ml.ident.split('/')))
        if not os.path.exists (outdir):
            os.makedirs (outdir)
        for msg in mbox:
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
            post.forum_ident = ml.ident
            post.name = decode_header (msgsubject)

            if msgparent is not None:
                msgparent = blip.utils.utf8dec (email.utils.parseaddr (msgparent)[1])
                pident = ml.ident + u'/' + msgparent
                parent = blip.db.ForumPost.get_or_create (pident, u'ListPost')
                parent.forum = ml
                post.parent_ident = parent.ident

            msgfrom = email.utils.parseaddr (msgfrom)
            personident = blip.utils.utf8dec (msgfrom[1])
            person = blip.db.Entity.get_or_create_email (personident)
            person.extend (name=decode_header(msgfrom[0]))
            post.author_ident = person.ident
            if person.ident != personident:
                post.person_alias_ident = personident
            blip.db.Queue.push (person.ident)

            # The Date header is screwed up way too often. We'll get the
            # date from the Received header, if at all possible.
            dt = None
            msgreceived = msg.get_all ('Received')
            if msgreceived is not None:
                for received in msgreceived:
                    try:
                        received = re.sub ('\(.*', '', received.split(';')[-1]).strip()
                        received = email.utils.parsedate_tz (received)
                        rdt = datetime.datetime (*received[:6])
                        if received[-1] is not None:
                            rdt = rdt + datetime.timedelta (seconds=received[-1])
                        if rdt is not None and rdt >= clamp[0] and rdt <= clamp[1]:
                            dt = rdt
                            break
                    except:
                        rdt = None
            # Sometimes the Received header is just as flaky. If the year is
            # two digits, assume fire rained from the sky on Y2K.
            if dt is not None and dt.year < 100:
                tup = dt.timetuple ()
                dt = datetime.datetime (tup.tm_year + 1900, tup.tm_mon, tup.tm_mday,
                                        tup.tm_hour, tup.tm_min, tup.tm_sec)
            # If Received is still giving us garbage, try Date, I guess.
            if dt is None or dt < clamp[0] or dt > clamp[1]:
                msgdate = email.utils.parsedate_tz (msgdate)
                try:
                    dt = datetime.datetime (*msgdate[:6])
                    if msgdate[-1] is not None:
                        dt = dt + datetime.timedelta (seconds=msgdate[-1])
                except:
                    dt = None
            post.datetime = dt
            post.weeknum = blip.utils.weeknum (dt)
            post.make_messages ()

            msgdesc = ''
            for msgpart in msg.walk():
                if msgpart.get_content_type() == 'text/plain':
                    msgtext = msgpart.get_payload()
                    seencmt = False
                    deldesc = True
                    for msgline in msgtext.split('\n'):
                        if len(msgdesc) > 250:
                            break
                        if msgline.startswith('>'):
                            if not seencmt and len(msgdesc) < 80:
                                deldesc = True
                            seencmt = True
                            continue
                        if len(msgline) > 0:
                            if deldesc:
                                msgdesc = ''
                                deldesc = False
                            msgdesc += msgline + ' '
                    post.desc = blip.utils.utf8dec (msgdesc)
                    break

            blip.db.flush()
            post.decache()

            outfile = open (os.path.join(outdir, score_encode (msgid)), 'w')
            outfile.write (msg.as_string())
            outfile.close()


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
        data = blip.utils.utf8dec (data)
        data = re.sub ('[\n\s]+', ' ', data).strip ()
        if data.startswith (self._listname + ' -- '):
            self.title = data[len(self._listname) + 4:]


class HeadRequest (urllib2.Request):
    # FIXME: redirects do a GET, and redirects pretty much
    # always happen the way we're constructing URLs below.
    def get_method (self):
        return 'HEAD'


class ListsDoapHandler (blip.plugins.doap.sweep.DoapHandler):
    def process_model (self, model):
        rels = []
        query = RDF.SPARQLQuery(' PREFIX doap: <http://usefulinc.com/ns/doap#>'
                                ' SELECT ?ml'
                                ' WHERE {'
                                '  ?project a doap:Project ;'
                                '    doap:mailing-list ?ml .'
                                ' } LIMIT 1')
        for defs in query.execute (model):
            uri = unicode(defs['ml'].uri)
            split = uri.split('/')
            if len(split) != 6:
                return
            if split[3] != 'mailman' or split[4] != 'listinfo':
                return
            domain = blip.utils.utf8dec(split[2])
            if domain.startswith(u'mail.'):
                domain = domain[5:]
            elif domain.startswith(u'lists.'):
                domain = domain[6:]
            mlid = blip.utils.utf8dec(split[5])
            ident = u'/' + u'/'.join(['list', domain, mlid])
            ml = blip.db.Forum.get_or_create (ident, u'List')
            ml.extend ({'name': mlid})
            ml.data['listinfo'] = uri
            if ml.data.get('archive') is None:
                try:
                    archive = uri.replace('mailman/listinfo', 'archives')
                    httpres = urllib2.urlopen(HeadRequest(archive))
                    ml.data['archive'] = httpres.geturl()
                    httpres.close ()
                except urllib2.HTTPError:
                    pass
            if ml.data.get('archive') is None:
                try:
                    archive = uri.replace('mailman/listinfo', 'pipermail')
                    httpres = urllib2.urlopen(HeadRequest(archive))
                    ml.data['archive'] = httpres.geturl()
                    httpres.close ()
                except urllib2.HTTPError:
                    pass
            rels.append(blip.db.BranchForum.set_related (self.scanner.branch, ml))
        self.scanner.branch.set_relations (blip.db.BranchForum, rels)
