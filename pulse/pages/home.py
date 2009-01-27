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

import pulse.config
import pulse.html
import pulse.models as db
import pulse.utils

def main (path, query, http=True, fd=None):
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}

    if query.get('ajax', None) == 'tab':
        return output_ajax_tab (**kw)
    else:
        return output_home (**kw)


def output_home (**kw):
    page = pulse.html.Page (http=kw.get('http', True),
                            url=(pulse.config.web_root + 'home'))
    page.set_title (pulse.utils.gettext ('Home'))

    page.add_tab ('ticker', pulse.utils.gettext ('Ticker'))
    box = get_ticker_tab (**kw)
    page.add_to_tab ('ticker', box)

    page.output (fd=kw.get('fd'))


def output_ajax_tab (**kw):
    query = kw.get ('query', {})
    page = pulse.html.Fragment (http=kw.get('http', True))
    tab = query.get('tab', None)
    if tab == 'ticker':
        page.add_content (get_ticker_tab (**kw))
    page.output(fd=kw.get('fd'))
    return 0


def get_ticker_tab (**kw):
    box = pulse.html.Div ('This is your ticker')
    return box
