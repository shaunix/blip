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

"""Output information about transltions"""

import datetime
import math
import os

import pulse.config
import pulse.graphs
import pulse.html
import pulse.models as db
import pulse.scm
import pulse.utils

people_cache = {}

def main (path, query, http=True, fd=None):
    """Output information about translations"""
    ident = '/' + '/'.join(path)
    if len(path) == 7:
        po = db.Branch.objects.filter (ident=ident)
        try:
            po = po[0]
            branchable = po.branchable
        except IndexError:
            po = branchable = None
    elif len(path) == 6:
        branchable = db.Branchable.objects.filter (ident=ident)
        try:
            branchable = branchable[0]
            po = branchable.default
        except IndexError:
            po = branchable = None
    else:
        kw = {'http' : http}
        kw['title'] = pulse.utils.gettext ('Invalid Identifier')
        page = pulse.html.PageError (
            pulse.utils.gettext ('The identifier %s is not valid') % ident,
            **kw)
        page.output (fd=fd)
        return 500

    if po == None:
        kw = {'http' : http}
        kw['title'] = pulse.utils.gettext ('Translation Not Found')
        page = pulse.html.PageNotFound (
            pulse.tuils.gettext ('No document with the identifier %s could be found')
            % ident,
            **kw)
        page.output (fd=fd)
        return 404
        
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    return output_translation (po, branchable, **kw)


def output_translation (po, branchable, **kw):
    """Output information about a translation"""
    page = pulse.html.RecordPage (po, http=kw.get('http', True))
    checkout = pulse.scm.Checkout.from_record (po, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(branchable.branches.all()), 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != po.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    # Facts
    parent = po.parent
    module = parent.parent
    page.add_fact (pulse.utils.gettext ('Module'), module)
    if parent.type == 'Document':
        page.add_fact (pulse.utils.gettext ('Document'), parent)
    else:
        page.add_fact (pulse.utils.gettext ('Domain'), parent)

    page.add_fact_sep ()
    page.add_fact (pulse.utils.gettext ('Location'),
                   checkout.get_location (po.scm_dir, po.scm_file))
    if po.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (po.mod_datetime.strftime('%Y-%m-%d %T'))
        if po.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (po.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    page.output(fd=kw.get('fd'))

    return 0
