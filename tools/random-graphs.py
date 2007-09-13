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

import os
from random import random, randint
import sys
sys.path.append ('..')

import pulse.config as config
import pulse.db as db
import pulse.graphs as graphs

def drawRandom (ident, png):
    dir = [config.webdir, 'graphs']
    dir.extend (ident.split ('/'))
    dir = os.path.join (*dir)
    file = os.path.join (dir, png)
    if not os.access (dir, os.F_OK):
        os.makedirs (dir)
    data = [random()]
    for i in range (0, 15):
        pm = randint(0, 1) * (1.0 - data[i])
        if pm > 0.7:
            pt = data[i] + (random() * (1.0 - data[i]))
        else:
            pt = data[i] - (random() * (data[i] - 0.0))
        data.append (pt)
    graphs.drawPulse (file, data)

if __name__ == '__main__':
    modules = db.Module.select ()
    for module in modules:
        drawRandom (module.ident, 'rcs.png')
        drawRandom (module.ident, 'ml.png')

        branches = db.Branch.select (db.Branch.q.moduleID == module.id)
        for branch in branches:
            drawRandom (branch.ident, 'rcs.png')
            drawRandom (branch.ident, 'ml.png')
            
    people = db.Person.select ()
    for person in people:
        drawRandom (person.ident, 'rcs.png')
        drawRandom (person.ident, 'ml.png')

    lists = db.MailList.select ()
    for list in lists:
        drawRandom (list.ident, 'all.png')
