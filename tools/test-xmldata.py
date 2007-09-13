#!/usr/bin/env python
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

import sys
sys.path.append ('..')

import pulse.config as config
import pulse.xmldata as xmldata

def ellipsize (str):
    if len(str) > 60:
        return str[0:58] + '...'
    else:
        return str

def printNode (node, depth=0):
    tab = '  ' * depth
    print (tab + '%(id)s (%(__type__)s):' %node)
    tab += '  '
    for k in node.keys ():
        if k.startswith ('__'): continue
        str = tab + k
        if isinstance (node[k], basestring):
            str += ': ' + ellipsize (node[k])
            print str
        elif isinstance (node[k], dict):
            str += ' (DICT):'
            print str
            for n in node[k].values():
                printNode (n, depth+2)
        elif isinstance (node[k], list):
            str += ' (LIST):'
            print str
            for item in node[k]:
                print (tab + '  ' + item)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        file = sys.argv[1]
    else:
        file = config.datadir ('xml/modules.xml')
    nodes = xmldata.getData (file)
    for key in nodes.keys():
        printNode (nodes[key])

