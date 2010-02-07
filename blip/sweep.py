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

import blip.core


def print_error (msg):
    print >>sys.stderr, '%s: %s' % (os.path.basename (sys.argv[0]), msg)


class OptionParser (optparse.OptionParser):
    def print_help (self, request, formatter=None):
        tool = request.get_tool_name()
        if tool is None:
            self.set_usage ('%prog [common options] <command> [command options]')
            optparse.OptionParser.print_help (self, formatter)
            print '\nCommands:'
            for cmd in SweepResponder.get_extensions ():
                if cmd.command is None:
                    continue
                line = '  ' + cmd.command
                if cmd.synopsis is not None:
                    line += '    ' + cmd.synopsis
                print line
        else:
            self.set_usage ('%prog [common options] ' + tool + ' [command options]')
            optparse.OptionParser.print_help (self, formatter)

class CommonFormatter (optparse.IndentedHelpFormatter):
    def format_heading (self, heading):
        return 'Common Options:\n'

class ToolFormatter (optparse.IndentedHelpFormatter):
    def format_usage (self, usage):
        return ''

    def format_heading (self, heading):
        return 'Command Options:\n'


class SweepRequest (blip.core.Request):
    def __init__ (self, args=sys.argv[1:]):
        self._common_parser = OptionParser (formatter=CommonFormatter())
        self._common_parser.disable_interspersed_args ()
        self._common_parser.remove_option ('-h')
        self._common_parser.add_option ('-h', '--help',
                                        dest='_is_help_request',
                                        action='store_true',
                                        default=False,
                                        help='print this help message and exit')
        self._tool_parser = OptionParser (formatter=ToolFormatter())
        self._tool_parser.remove_option ('-h')
        self._tool = None
        self._common_options = {}
        self._common_args = []
        self._tool_options = {}
        self._tool_args = []

    def add_common_option (self, *args, **kw):
        self._common_parser.add_option (*args, **kw)

    def add_tool_option (self, *args, **kw):
        self._tool_parser.add_option (*args, **kw)

    def parse_common_options (self, args=sys.argv[1:]):
        (self._common_options, args) = self._common_parser.parse_args (args)
        if len(args) > 0:
            self._tool = args[0]
            self._common_args = args[1:]

    def parse_tool_options (self, args=None):
        if args is None:
            (self._tool_options, self._tool_args) = self._tool_parser.parse_args (self._common_args)
        else:
            (self._tool_options, self._tool_args) = self._tool_parser.parse_args (args)

    def is_help_request (self):
        return self._common_options._is_help_request

    def print_help (self):
        self._common_parser.print_help (self)
        if self._tool is not None:
            self._tool_parser.print_help (self)

    def get_tool_name (self):
        return self._tool

    def get_common_option (self, option, default=None):
        pass

    def get_tool_option (self, option, default=None):
        pass


class SweepResponse (blip.core.Response):
    def __init__ (self, request):
        blip.core.Response.__init__ (self, request)
        self._error_text = None

    def get_error_text (self):
        return self._error_text

    def set_error_text (self, error):
        self._error_text = error


class SweepResponder (blip.core.Responder):
    command = None
    synopsis = None

    @classmethod
    def run (cls, request, args=sys.argv[1:]):
        blip.core.import_plugins ('sweep')

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
        request.parse_common_options (args)

        tool = request.get_tool_name ()
        help = request.is_help_request ()

        responder = None
        if tool is not None:
            for cmd in SweepResponder.get_extensions ():
                if cmd.command == tool:
                    responder = cmd
                    break
        if responder is None and tool is not None:
            response = SweepResponse ()
            response.set_error_text ('%s is not a blip-sweep command.' % tool)
            response.set_return_code (1)
            return response

        if responder is not None:
            try:
                responder.add_tool_options (request)
            except NotImplementedError:
                pass

        if help:
            request.print_help ()
            return SweepResponse ()

        if responder is None:
            request.print_help ()
            response = SweepResponse ()
            response.set_error_text ('No blip-sweep command supplied.')
            response.set_return_code (1)
            return response

        if request.is_help_request():
            request.print_help ()
            return SweepResponse ()

        response = responder.respond (request)
        return response

    @classmethod
    def add_tool_options (cls, request):
        raise NotImplementedError ('%s does not provide the add_tool_options method.'
                                   % cls.__name__)



