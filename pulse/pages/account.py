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
    if path[1] == 'new':
        return output_account_new (**kw)


def output_account_new (**kw):
    page = pulse.html.Page (http=kw.get('http', True))
    page.set_title (pulse.utils.gettext ('Create New Account'))

    columns = pulse.html.ColumnBox (2)
    page.add_content (columns)

    section = pulse.html.SectionBox (pulse.utils.gettext ('Create an Account'))
    columns.add_to_column (0, section)

    table = pulse.html.Table ()
    section.add_content (table)

    table.add_row (
        pulse.utils.gettext ('Name:'),
        pulse.html.TextInput ('realname') )
    table.add_row (
        pulse.utils.gettext ('Username:'),
        pulse.html.TextInput ('username') )
    table.add_row (
        pulse.utils.gettext ('Email:'),
        pulse.html.TextInput ('email') )
    table.add_row (
        pulse.utils.gettext ('Password:'),
        pulse.html.TextInput ('password1', password=True) )
    table.add_row (
        pulse.utils.gettext ('Confirm:'),
        pulse.html.TextInput ('password2', password=True) )
    table.add_row ('', pulse.html.SubmitButton ('create', 'Create'))

    section = pulse.html.SectionBox (pulse.utils.gettext ('Why Create an Account?'))
    columns.add_to_column (1, section)

    section.add_content (pulse.html.Div (pulse.utils.gettext (
        'Pulse automatically collects publicly-available information, ponders it,' +
        ' and outputs it in ways that are useful to human beings.  All of the' +
        ' information on Pulse is available to everybody.  You don\'t need an' +
        ' account to access any super-secret members-only content.  But creating' +
        ' an account on Pulse has other great advantages:'
        )))
    dl = pulse.html.DefinitionList ()
    section.add_content (dl)
    dl.add_bold_term (pulse.utils.gettext ('Mark your territory'))
    dl.add_entry (pulse.utils.gettext (
        'Every day, Pulse finds people identified only by their email addresses or' +
        ' usernames on various systems.  You can claim to be these unknown people,' +
        ' giving you the recognition you deserve and helping Pulse create more' +
        ' meaningful statistics.  Claims are reviewed by an actual human being;' +
        ' sorry, we can\'t all be Federico.'
        ))
    dl.add_bold_term (pulse.utils.gettext ('Watch the ones you love'))
    dl.add_entry (pulse.utils.gettext (
        'As a registered user, you can watch people, projects, and anything else' +
        ' with a pulse.  Updates to things you watch will show up in the Ticker' +
        ' on your personal start page.'
        ))
    dl.add_bold_term (pulse.utils.gettext ('Make Pulse smarter'))
    dl.add_entry (pulse.utils.gettext (
        'Pulse knows a lot, but you can help it know more about you by telling it' +
        ' things about yourself.  Better yet, you can point Pulse to places that' +
        ' already know about you, and we\'ll take care of the rest.'
        ))

    page.output (fd=kw.get('fd'))
