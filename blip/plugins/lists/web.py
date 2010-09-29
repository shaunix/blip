# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
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

import datetime
import os

import blinq.config
import blinq.utils

import blip.db
import blip.html
import blip.utils
import blip.web

import blip.plugins.index.web

class ListsIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response):
        """Construct an info box for the index page"""
        box = blip.html.SidebarBox (blip.utils.gettext ('Lists'))
        page.add_sidebar_content (box)

        #txt = (blip.utils.gettext ('Blip is watching %i mailing lists.') %
        #       blip.db.Forum.select (type=u'List').count() )
        #box.add_content (blip.html.Div (txt))

        mls = blip.db.Forum.select (type=u'List')

        active = mls.order_by (blip.db.Desc (blip.db.Forum.score))
        bl = blip.html.BulletList ()
        box.add_content (bl)
        for ml in active[:6]:
            bl.add_link (ml)

class ListReponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) != 3 or request.path[0] != 'list':
            return False
        ident = u'/' + u'/'.join(request.path)
        request.record = blip.db.Forum.get (ident)
        return True

    @classmethod
    def respond (cls, request):
        if len(request.path) != 3 or request.path[0] != 'list':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page
        return response

