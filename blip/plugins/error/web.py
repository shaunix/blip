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

import blinq.config
import blinq.utils

import blip.db
import blip.html
import blip.utils
import blip.web

import blip.plugins.index.web

################################################################################
## Pages

class ErrorResponder (blip.web.PageResponder):
    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) != 1 or request.path[0] != 'error':
            return None

        response = blip.web.WebResponse (request)

        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext ('Errors'))
        cont = blip.html.ContainerBox ()
        cont.set_show_icons (False)
        page.add_content (cont)

        errors = blip.db.Error.select ()
        errors = blinq.utils.attrsorted (list(errors), 'ident')
        for err in errors:
            req = blip.web.WebRequest (http=False,
                                       path_info=err.ident,
                                       query_string='')
            record = None
            for loc in blip.web.RecordLocator.get_extensions ():
                if loc.locate_record (req):
                    record = req.record
                    break

            if record is not None:
                lbox = cont.add_link_box (record)
            else:
                lbox = cont.add_link_box (None, err.ident)
            lbox.add_content (err.message)

        response.payload = page
        return response

class SetIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response, **kw):
        """Construct an info box for the index page"""
        cnt = blip.db.Error.select().count()
        if cnt == 0:
            return
        box = blip.html.SidebarBox (blip.utils.gettext ('Errors'))
        bl = blip.html.BulletList ()
        box.add_content (bl)
        bl.add_link (blinq.config.web_root_url + 'error',
                     blip.utils.gettext ('%i errors') % cnt)
        page.add_sidebar_content (box)
