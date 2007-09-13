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

# _dir and _url are simple utility classes to allow
# strings to be callable to do path joins.
class _dir (str):
    def __init__ (self, s):
        str.__init__ (self, s)
    def __call__ (self, *s):
        return _dir (os.path.join (self, *s))
class _url (str):
    def __init__ (self, s):
        str.__init__ (self, s)
    def __call__ (self, *s):
        if self.endswith ('/'):
            return _url (self + '/'.join(s))
        else:
            return _url (self + '/' + '/'.join(s))

datadir = _dir ('/shaunm/projects/pulse/data/')
vardir = _dir ('/shaunm/projects/pulse/var/')

potdir = vardir ('pot')
rcsdir = vardir ('rcs')

webdir = _dir ('/shaunm/projects/pulse/web/')
webroot = _url ('file:///shaunm/projects/pulse/web/')

# need dir2url to make this use vardir
dbroot = _url ('sqlite:/shaunm/projects/pulse/var/pulse.db')
#dbroot = _url( 'mysql://user:pass@localhost/pulse')
