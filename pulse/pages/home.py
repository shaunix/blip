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
    box.add_content (pulse.html.Div ('This is your ticker %s' % account.realname))
    bl = pulse.html.BulletList ()
    box.add_content (bl)
    for watch in db.AccountWatch.objects.filter (account=account):
        bl.add_item (watch.ident)
    return box
