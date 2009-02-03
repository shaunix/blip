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

import Cookie
import datetime
import os

import pulse.config
import pulse.html
import pulse.models as db
import pulse.response
import pulse.utils

def main (response, path, query):
    kw = {'path' : path, 'query' : query}

    # FIXME: verify response.http_account, else redirect to /account/login

    if query.get('ajax', None) == 'tab':
        output_ajax_tab (response, **kw)
    else:
        output_home (response, **kw)


def output_home (response, **kw):
    page = pulse.html.Page (url=(pulse.config.web_root + 'home'))
    page.set_title (pulse.utils.gettext ('Home'))
    if response.http_account != None:
        page.set_title (response.http_account.realname)

    page.add_tab ('ticker', pulse.utils.gettext ('Ticker'))
    box = get_ticker_tab (response.http_account, **kw)
    page.add_to_tab ('ticker', box)

    response.set_contents (page)


def output_ajax_tab (response, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'ticker':
        response.set_contents (get_ticker_tab (response.http_account, **kw))


def get_ticker_tab (account, **kw):
    box = pulse.html.Div ()
    watches = [watch.ident for watch in db.AccountWatch.objects.filter (account=account)]
    now = datetime.datetime.now ()
    messages = db.Message.objects.filter (subj__in=watches,
                                          datetime__gte=(now - datetime.timedelta (days=8)))
    messages = messages.order_by ('-datetime')
    weeknow = now.weekday ()
    weekday = None
    weekiter = 0
    for message in messages[:100]:
        mweekday = message.datetime.weekday()
        if weekday == None or mweekday != weekday:
            if weekiter > 6:
                break
            bl = pulse.html.BulletList ()
            if weekiter == 0:
                bl.set_title (pulse.utils.gettext ('Today'))
            elif weekiter == 1:
                bl.set_title (pulse.utils.gettext ('Yesterday'))
            else:
                title = [
                    pulse.utils.gettext ('Monday'),
                    pulse.utils.gettext ('Tuesday'),
                    pulse.utils.gettext ('Wednesday'),
                    pulse.utils.gettext ('Thursday'),
                    pulse.utils.gettext ('Friday'),
                    pulse.utils.gettext ('Saturday'),
                    pulse.utils.gettext ('Sunday')]
                bl.set_title (title[mweekday])
            box.add_content (bl)
            weekday = mweekday
            weekiter += 1
        if message.type == 'commit' and message.pred == None:
            span = pulse.html.Span ()
            span.add_content (pulse.utils.gettext ('%i commits were made to ') % message.count)
            span.add_content (pulse.html.Link (db.Branch.get_cached (message.subj)))
            bl.add_item (span)
    return box
