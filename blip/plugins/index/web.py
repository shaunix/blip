# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

import blinq.ext

import blip.html
import blip.web
import blip.utils

class IndexResponder (blip.web.PageResponder):
    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) != 0:
            return None

        response = blip.web.WebResponse (request)

        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext (''))
        cont = blip.html.PaddingBox ()
        page.add_content (cont)

        for provider in IndexContentProvider.get_extensions ():
            provider.provide_content (page, response)

        response.payload = page
        return response

class IndexContentProvider (blinq.ext.ExtensionPoint):
    @classmethod
    def provide_content (cls, page, response, **kw):
        pass
