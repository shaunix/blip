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

import os
from urllib import urlencode
from urllib2 import Request, urlopen
from urlparse import urlparse
import csv
import time

import pulse.db
from pulse.utils import URL, utf8dec

synop = 'update issue tracker information'
args = pulse.utils.odict()

MAP = {'bug_severity': 'severity',
       'bug_status': 'status',
       'short_desc': 'summary'}


def process(data):
    headers = []
    for name in data.next():
        headers.append(MAP.get(name, name))
    for line in data:
        bugtracker = 'bugzilla.gnome.org'
        this = dict(zip(headers, line))
        this['time'] = time.mktime(time.strptime(this['changeddate'], '%Y-%m-%d %H:%M:%S'))
        issue_ident = u'issue/%s/%s/%i' % (bugtracker, this['bug_id'], this['time'])
        issue = pulse.db.Issue.get_or_create (issue_ident)
        for key, value in this.items():
            if key in ('time', 'bug_id'):
                value = int(value)
            else:
                value = utf8dec(value)
            if hasattr(issue.__class__, key):
                setattr(issue, key, value)
        # component
        comp_ident = u'comp/%s/%s/%s' % (bugtracker, this['product'], this['component'])
        issue.comp = pulse.db.Component.get_or_create (comp_ident)
        issue.comp.name = utf8dec(this['component'])


def update():
    bugzilla = URL(netloc='bugzilla.gnome.org', path='/buglist.cgi')

    bugzilla['query_format'] = 'advanced'
    bugzilla['ctype'] = 'csv'
    # for example: bugzilla['product'] = 'Yelp'
    bugzilla['chfieldfrom'] = time.strftime('%Y-%m-%d', time.gmtime(time.time() - 7 * 24*60*60)) # TODO since last update
    bugzilla['chfieldto'] = 'Now'
    bugzilla['bug_status'] = ['UNCONFIRMED', 'NEW', 'ASSIGNED', 'REOPENED', 'NEEDINFO']

    headers = {'Cookie': 'COLUMNLIST=changeddate%20bug_severity%20priority%20bug_status%20resolution%20product%20component%20short_desc'}
    
    print str(bugzilla)
    
#    req = Request(str(bugzilla), None, headers)
#    open('/tmp/data.csv', 'w').write(urlopen(req).read())
#    data = csv.reader(urlopen(req))
#    data
    process(csv.reader(open('/tmp/data.csv')))
#    process(csv.reader(urllib.urlopen(url)))


################################################################################
## main

def main (argv, options=None):
    try:
        update ()
        pulse.db.flush ()
    except:
        pulse.db.rollback ()
        raise
    else:
        pulse.db.commit ()
        return 0



