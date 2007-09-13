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

import pulse.db as db
import pulse.html as html

def get_summary (doc):
    sum = html.SummaryDiv (doc)
    if doc.error != None:
        sum.add_block (html.Admonition (doc.error,
                                        'error'))
        return sum
    if doc.tool == None:
        sum.add_block (html.Admonition (
            'This document is managed with an unrecognized tool.',
            'error'))
        return sum
    if doc.status == None:
        sum.add_block (html.Admonition (
            'This document has no status information.',
            'warning'))
    tr = db.Translation.select (db.Translation.q.sourceID == doc.id)
    sum.add_block ('<div>%i translations</div>' % tr.count())
    return sum
