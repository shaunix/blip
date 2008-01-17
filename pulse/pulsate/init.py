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
import os.path
import sys

import pulse.config
import pulse.models

import django.core.management

synop = 'initialize the Pulse database'

def main (argv, options={}):
    for dir in (pulse.config.scratch_dir,
                pulse.config.web_graphs_dir,
                pulse.config.web_icons_dir,
                pulse.config.web_l10n_dir,
                pulse.config.web_screens_dir):
        if not os.path.exists (dir):
            os.makedirs (dir)
    django.core.management.syncdb (0, False)
