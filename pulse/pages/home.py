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

    if response.http_account == None:
        response.redirect (pulse.config.web_root + 'account/login')
        return

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

    page.add_tab ('watches', pulse.utils.gettext ('Watches'))

    response.set_contents (page)


def output_ajax_tab (response, **kw):
    query = kw.get ('query', {})
    tab = query.get('tab', None)
    if tab == 'ticker':
        response.set_contents (get_ticker_tab (response.http_account, **kw))
    elif tab == 'watches':
        response.set_contents (get_watches_tab (response.http_account, **kw))


def get_ticker_tab (account, **kw):
    box = pulse.html.Div ()
    watches = [watch.ident for watch in db.AccountWatch.objects.filter (account=account)]
    now = datetime.datetime.now ()

    populate_caches (watches)
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
            if weekiter == 0:
                title = pulse.utils.gettext ('Today')
            elif weekiter == 1:
                title = pulse.utils.gettext ('Yesterday')
            else:
                title = [
                    pulse.utils.gettext ('Monday'),
                    pulse.utils.gettext ('Tuesday'),
                    pulse.utils.gettext ('Wednesday'),
                    pulse.utils.gettext ('Thursday'),
                    pulse.utils.gettext ('Friday'),
                    pulse.utils.gettext ('Saturday'),
                    pulse.utils.gettext ('Sunday')]
                title = title[mweekday]
            ticker = pulse.html.TickerBox (title)
            box.add_content (ticker)
            weekday = mweekday
            weekiter += 1
        try:
            if message.type == 'commit':
                if message.subj == None:
                    continue
                elif message.pred == None:
                    span = pulse.html.Span ()
                    branch = db.Branch.get_cached (message.subj)
                    span.add_content (pulse.html.Link (branch))
                    span.add_content (pulse.utils.gettext ('had %i commits on %s.') %
                                      (message.count, branch.scm_branch))
                    ticker.add_event (span, icon=branch.get_icon_url())
                else:
                    span = pulse.html.Span ()
                    person = db.Entity.get_cached (message.subj)
                    branch = db.Branch.get_cached (message.pred)
                    span.add_content (pulse.html.Link (person))
                    span.add_content (pulse.utils.gettext (' made %i commits to ') % message.count)
                    span.add_content (pulse.html.Link (branch))
                    span.add_content (pulse.utils.gettext (' on %s.') % branch.scm_branch)
                    ticker.add_event (span, icon=person.get_icon_url())
        except:
            pass
    return box


def get_watches_tab (account, **kw):
    cont = pulse.html.PaddingBox ()
    box = pulse.html.IconBox ()
    cont.add_content (box)
    box.set_title (pulse.utils.gettext ('What You Watch'))

    watches = [watch.ident for watch in db.AccountWatch.objects.filter (account=account)]
    populate_caches (watches)
    watches = [db.get_by_ident (watch) for watch in watches]

    watches = pulse.utils.attrsorted (watches, 'title')
    for record in watches:
        box.add_link (record)

    box = pulse.html.IconBox ()
    cont.add_content (box)
    box.set_title (pulse.utils.gettext ('Who Watches You'))
    watches = list(db.AccountWatch.objects.filter (ident=account.person.ident))
    watches = pulse.utils.attrsorted ([db.Entity.get_cached (watch.ident) for watch in watches], 'title')
    if len(watches) == 0:
        box.add_content (pulse.utils.gettext ('Nobody is watching you'))
    else:
        for record in watches:
            box.add_link (record)

    return cont


def populate_caches (idents):
    people = [ident for ident in idents if ident.startswith('/person/')]
    if len(people) > 0:
        people = db.Entity.objects.filter (ident__in=people)
        for person in list(people):
            db.Entity.set_cached (person.ident, person)

    branches = [ident for ident in idents if ident.startswith('/mod/')]
    if len(branches) > 0:
        branches = db.Branch.objects.filter (ident__in=branches)
        for branch in list(branches):
            db.Branch.set_cached (branch.ident, branch)

