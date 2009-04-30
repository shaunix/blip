# Copyright (c) 2006-2009  Shaun McCance  <shaunm@gnome.org>
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

from pulse import core, html, pages, utils

class IndexHandler (core.RequestHandler):
    def initialize (self):
        pass

    def handle_request (self):
        page = html.Page ()
        page.set_title (utils.gettext ('Pulse'))
        cont = html.PaddingBox ()
        page.add_content (cont)
        types = pages.__all__
        mods = [utils.import_ ('pulse.pages.' + t) for t in types]
        for mod in mods:
            if not hasattr(mod, 'synopsis_sort'):
                setattr (mod, 'synopsis_sort', 0)
        for mod in sorted (mods,
                           cmp=(lambda x, y:
                                cmp(x.synopsis_sort, y.synopsis_sort) or
                                cmp(x.__name__, y.__name__))):
            if hasattr (mod, 'synopsis'):
                box = mod.synopsis ()
                if isinstance (box, html.SidebarBox):
                    page.add_sidebar_content (box)
                else:
                    cont.add_content (box)
        self.response.set_contents (page)

def get_request_handler (request, response):
    return IndexHandler (request, response)
