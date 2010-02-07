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

import blip.html
import blip.web
import blip.utils

class IndexHandler (blip.web.PageHandler):
    @classmethod
    def handle_request (cls, request):
        page = blip.html.Page ()
        page.set_title (blip.utils.gettext ('Blip'))
        cont = blip.html.PaddingBox ()
        page.add_content (cont)

        # FIXME: instead of this old stuff, we'll provide an extension
        # point for index page boxes.
        #types = pages.__all__
        #mods = [utils.import_ ('blip.pages.' + t) for t in types]
        #for mod in mods:
        #    if not hasattr(mod, 'synopsis_sort'):
        #        setattr (mod, 'synopsis_sort', 0)
        #for mod in sorted (mods,
        #                   cmp=(lambda x, y:
        #                        cmp(x.synopsis_sort, y.synopsis_sort) or
        #                        cmp(x.__name__, y.__name__))):
        #    if hasattr (mod, 'synopsis'):
        #        box = mod.synopsis ()
        #        if isinstance (box, html.SidebarBox):
        #            page.add_sidebar_content (box)
        #        else:
        #            cont.add_content (box)

        response = blip.web.WebResponse (request)
        response.set_widget (page)
        return response
