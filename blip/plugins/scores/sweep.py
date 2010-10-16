# Copyright (c) 2010  Shaun McCance  <shaunm@gnome.org>
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

import blip.db
import blip.scm
import blip.sweep
import blip.utils

import blip.plugins.queue.sweep

class ScoreResponder (blip.sweep.SweepResponder):
    command = 'scores'
    synopsis = 'update project scores'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] modules [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        pass

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)
        argv = request.get_tool_args ()
        ident = None
        if len(argv) > 0:
            ident = blip.utils.utf8dec (argv[0])
        for updater in ScoreUpdater.get_extensions():
            updater.update_scores (request, ident)
        blip.db.commit()
        return response

class ScoreUpdater (blinq.ext.ExtensionPoint):
    @classmethod
    def update_scores (cls, request, ident):
        pass
