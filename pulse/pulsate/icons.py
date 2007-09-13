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

from httplib import HTTPConnection
import re
import sys

import pulse.db as db

synop = 'find icons in standard locations'
def usage (fd=sys.stderr):
    print >>fd, ('Usage: %s icons' % sys.argv[0])

def updateIcon (resource):
    url = resource.download + resource.rcs_module + '.png'
    match = re.match ('^http://([^/]*)(/.*)', url)
    if match:
        conn = HTTPConnection (match.group(1))
        conn.request ('HEAD', match.group(2))
        if conn.getresponse().status == 200:
            resource.set (icon = url)

def main (argv):
    # Module icons are checked in a set location relative to
    # their download URL.
    modules = db.Module.select()
    for module in modules:
        updateIcon (module)

    # If a list is only the list for one other resource, then
    # we let that list have that resource's icon.
    lists = db.MailList.select()
    for list in lists:
        src = list.get_related ('mail_list', invert=True)
        if len(src) == 1:
            icon = src[0].resource.icon
            if icon != None:
                list.icon = icon

    return 0
