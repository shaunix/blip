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

import os
import sys

import pulse.response as core

class TabProvider (core.Application):
    def __init__ (self, handler):
        super (TabProvider, self).__init__ (handler)

    def get_tab_title (self):
        raise NotImplementedError ('%s does not provide the get_tab_title method.'
                                   % self.__class__.__name__)

__all__ = []

for f in os.listdir (os.path.dirname (sys.modules[__name__].__file__)):
    if f.endswith ('.py'):
        tool = os.path.basename (f)[:-3]
    elif f.endswith ('.pyc'):
        tool = os.path.basename (f)[:-4]
    else:
        continue
    if not tool in __all__:
        __all__.append (tool)
