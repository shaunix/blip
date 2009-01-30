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

def main (path, query):
    kw = {'path' : path, 'query' : query}

    if query.get('ajax', None) == 'tab':
        return output_ajax_tab (**kw)
    else:
        return output_home (**kw)


def output_home (**kw):
    page = pulse.html.Page (url=(pulse.config.web_root + 'home'))
    page.set_title (pulse.utils.gettext ('Home'))
    if pulse.response.user_account != None:
        page.set_title (pulse.response.user_account.realname)

    page.add_tab ('ticker', pulse.utils.gettext ('Ticker'))
    box = get_ticker_tab (**kw)
    page.add_to_tab ('ticker', box)

    page.output ()


def output_ajax_tab (**kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment ()
    tab = query.get('tab', None)
    if tab == 'ticker':
        page.add_content (get_ticker_tab (**kw))
    page.output ()
    return 0


def get_ticker_tab (**kw):
    if pulse.response.user_account != None:
        box = pulse.html.Div ('This is your ticker %s' % pulse.response.user_account.realname)
    else:
        box = pulse.html.Div ('foo')
    return box
