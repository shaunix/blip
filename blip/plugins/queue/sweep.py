# Copyright (c) 2008-2009  Shaun McCance  <shaunm@gnome.org>
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

"""
Update information for queued objects
"""

import datetime

import blinq.ext

import blip.db
import blip.sweep
import blip.utils


class QueueHandler (blinq.ext.ExtensionPoint):
    @classmethod
    def process_queued (cls, ident, request):
        pass


class QueueResponder (blip.sweep.SweepResponder):
    command = 'queue'
    synopsis = 'update information for queued objects'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] queue [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--length',
                                 dest='queue_length',
                                 action='store_true',
                                 default=False,
                                 help='print the length of the queue and exit')
        request.add_tool_option ('--list',
                                 dest='queue_list',
                                 action='store_true',
                                 default=False,
                                 help='list the matching items in the queue and exit')
        request.add_tool_option ('--limit',
                                 dest='queue_limit',
                                 metavar='NUM',
                                 help='process at most NUM entries from the queue')
        request.add_tool_option ('--time-limit',
                                 dest='queue_time_limit',
                                 metavar='SECONDS',
                                 help='process the queue for at most SECONDS seconds')
        request.add_tool_option ('--no-history',
                                 dest='read_history',
                                 action='store_false',
                                 default=True,
                                 help='do not check SCM history')
        request.add_tool_option ('--no-timestamps',
                                 dest='timestamps',
                                 action='store_false',
                                 default=True,
                                 help='do not check timestamps before processing files')
        request.add_tool_option ('--no-update',
                                 dest='update_scm',
                                 action='store_false',
                                 default=True,
                                 help='do not update SCM repositories')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)
        argv = request.get_tool_args ()
        idents = []
        if len(argv) == 0:
            idents = [obj.ident for obj in blip.db.Queue.select ()]
        else:
            for arg in argv:
                ident = blip.utils.utf8dec (arg)
                idents += [obj.ident for obj in
                           blip.db.Queue.select (blip.db.Queue.ident.like (ident))]

        if request.get_tool_option ('queue_length'):
            print len(idents)
            return response

        if request.get_tool_option ('queue_list'):
            for ident in idents:
                print ident
            return response

        limit = request.get_tool_option ('queue_limit')
        if limit is not None:
            limit = int(limit)
            idents = idents[:limit]

        timelimit = request.get_tool_option ('queue_time_limit')
        if timelimit is not None:
            sep = timelimit.rfind (':')
            tlhour = tlmin = tlsec = 0
            if sep >= 0:
                tlsec = int(timelimit[sep+1:])
                tlpre = timelimit[:sep]
                sep = tlpre.rfind (':')
                if sep >= 0:
                    tlmin = int(tlpre[sep+1:])
                    tlhour = int(tlpre[:sep])
                else:
                    tlmin = int(tlpre)
            else:
                tlsec = int(timelimit)
            timelimit = 3600 * tlhour + 60 * tlmin + tlsec
        timestart = datetime.datetime.now()

        ident_i = 0
        for ident in idents:
            try:
                blip.utils.log ('Poppping from queue: %s' % ident)
                for cls in QueueHandler.get_extensions ():
                    cls.process_queued (ident, request)
                blip.db.Queue.pop (ident)
            except:
                blip.db.rollback ()
                raise
            else:
                blip.db.commit ()
            ident_i += 1
            if (timelimit is not None and
                (datetime.datetime.now() - timestart).seconds > timelimit):
                break;

        diff = datetime.datetime.now () - timestart
        diff = datetime.timedelta (days=diff.days, seconds=diff.seconds)
        blip.utils.log ('Queue processed %i records in %s' % (ident_i, diff))

        return response
