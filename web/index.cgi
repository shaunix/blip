#!/usr/bin/env python
# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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
import sys

import blip.db
import blip.html
import blip.utils
import blip.web


def main ():
    blip.db.block_implicit_flushes ()
    blip.utils.set_log_level (None)

    parser = optparse.OptionParser ()
    parser.set_usage ('Usage: %prog [options] [PATHINFO [QUERYSTRING]]')
    parser.add_option ('-o', '--output',
                       dest='output',
                       action='store',
                       default=None,
                       metavar='FILE',
                       help='output to the file FILE')
    parser.add_option ('--log-file',
                       dest='log_file',
                       action='store',
                       default=None,
                       metavar='FILE',
                       help='append log messages to FILE')
    parser.add_option ('--log-level',
                       dest='log_level',
                       action='store',
                       default='log',
                       metavar='LEVEL',
                       help='minimum log level to print; one of warn, log, or none [default=log]')
    parser.add_option ('--debug-db',
                       dest='debug_db',
                       action='store_true',
                       default=False,
                       help='print database queries to stdout')
    parser.add_option ('--debug-db-summary',
                       dest='debug_db_summary',
                       action='store_true',
                       default=False,
                       help='print summary of database queries to stdout')
    (options, args) = parser.parse_args ()

    if options.debug_db:
        blip.db.debug ()

    kw = {}
    if len(args) > 0:
        kw['http'] = False
        kw['path_info'] = args[0]
        if len(args) > 1:
            kw['query_string'] = args[1]

    if kw.get ('http', True):
        blip.utils.set_log_level (None)
    else:
        blip.utils.set_log_level (options.log_level)
        if options.log_file is not None:
            blip.utils.set_log_file (options.log_file)
        
    request = blip.web.WebRequest (**kw)

    #try:
    #    token = request.cookies.get ('pulse_auth')
    #    token = utils.utf8dec (token.value)
    #    response.http_login = db.Login.get_login (token, os.getenv ('REMOTE_ADDR'))
    #    response.http_account = response.http_login.account
    #except:
    #    pass

    response = blip.web.WebResponder.respond (request)

    if options.debug_db_summary:
        blip.db.debug_summary ()

    if options.output is not None:
        fd = open (options.output, 'w')
    else:
        fd = None
    response.output (fd=fd)

    blip.db.rollback ()
    sys.exit (response.get_return_code ())


if __name__ == "__main__":
    main ()
