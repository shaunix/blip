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

import pulse.db
import pulse.utils

synop = 'update information for queued objects'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['length'] = (None, 'print the length of the queue and exit')
args['limit='] = ('num', 'process at most num entries from the queue')
args['time-limit='] = ('time', 'process the queue for at most time seconds')
args['no-history'] = (None, 'do not check SCM history')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-docs'] = (None, 'do not update the documentation')
args['no-i18n'] = (None, 'do not update the translations')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only records with a matching identifier will be updated.'


def main (argv, options={}):
    if len(argv) == 0:
        ident = None
    else:
        ident = pulse.utils.utf8dec (argv[0])
    length = options.get ('--length', False)
    if length:
        if ident is not None:
            print pulse.db.Queue.select(pulse.db.Queue.ident.like (ident)).count()
        else:
            print pulse.db.Queue.select().count()
        return 0
    limit = options.get ('--limit', None)
    if limit is not None:
        limit = int(limit)
    timelimit = options.get ('--time-limit', None)
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
        import datetime
        timestart = datetime.datetime.now()
    iter = 0
    el = pulse.db.Queue.pop (ident)
    while el != None:
        if limit != None and iter >= limit:
            return 0
        if timelimit != None and (datetime.datetime.now() - timestart).seconds > timelimit:
            return 0
        iter += 1
        mod = pulse.utils.import_ ('pulse.pulsate.' + el['module'])
        if hasattr (mod, 'args'):
            ret = mod.main ([el['ident']], options)
        else:
            ret = mod.main ([el['ident']])
        if ret != 0:
            return ret
        el = pulse.db.Queue.pop (ident)
    return 0
