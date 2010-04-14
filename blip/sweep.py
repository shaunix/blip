# -*- coding: utf-8 -*-
# Copyright (c) 2008-2010  Shaun McCance  <shaunm@gnome.org>
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

import optparse
import os.path
import sys

import blinq.ext
import blinq.reqs.cmd


class SweepRequest (blinq.reqs.cmd.CmdRequest):
    pass


class SweepResponse (blinq.reqs.cmd.CmdResponse):
    pass


class SweepResponder (blinq.reqs.cmd.CmdResponder):
    @classmethod
    def respond (cls, request):
        request.add_common_option ('--log-file',
                                   dest='log_file',
                                   action='store',
                                   default=None,
                                   metavar='FILE',
                                   help='append log messages to FILE')
        request.add_common_option ('--log-level',
                                   dest='log_level',
                                   action='store',
                                   default='log',
                                   metavar='LEVEL',
                                   help='minimum log level to print; one of warn, log, or none [default=log]')
        request.add_common_option ('--debug-db',
                                   dest='debug_db',
                                   action='store_true',
                                   default=False,
                                   help='print database queries to stdout')
        request.add_common_option ('--debug-db-summary',
                                   dest='debug_db_summary',
                                   action='store_true',
                                   default=False,
                                   help='print summary of database queries to stdout')
        request.add_common_option ('--disable-plugins',
                                   dest='disable_plugins',
                                   action='store',
                                   default='',
                                   metavar='PLUGINS',
                                   help='disable plugins from comma-separated PLUGINS list')
        request.add_common_option ('--rollback',
                                   dest='rollback',
                                   action='store_true',
                                   default=False,
                                   help='roll back all changes (dry run)')
        request.parse_common_options ()

        import blip.plugins
        blinq.ext.import_extensions (blip.plugins, 'sweep')
        for tool in SweepResponder.get_extensions ():
            if tool.command is not None:
                request.add_tool_responder (tool)

        return blinq.reqs.cmd.CmdResponder.respond (request)
