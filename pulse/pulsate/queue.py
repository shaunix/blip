# Copyright (c) 2008  Shaun McCance  <shaunm@gnome.org>
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

import pulse.models as db
import pulse.utils

synop = 'update information for queued objects'
usage_extra = ''
args = pulse.utils.odict()
args['length'] = (None, 'print the length of the queue and exit')
args['limit='] = ('num', 'process at most num entries from the queue')
args['no-history'] = (None, 'do not check SCM history')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-docs'] = (None, 'do not update the documentation')
args['no-i18n'] = (None, 'do not update the translations')
def help_extra (fd=None):
    pass


def main (argv, options={}):
    length = options.get ('--length', False)
    if length:
        print db.Queue.objects.count()
        return
    limit = options.get ('--limit', None)
    if limit != None:
        limit = int(limit)
    iter = 0
    el = db.Queue.pop ()
    while el != None:
        if limit != None and iter >= limit:
            return
        iter += 1
        mod = pulse.utils.import_ ('pulse.pulsate.' + el['module'])
        if hasattr (mod, 'args'):
            mod.main ([el['ident']], options)
        else:
            mod.main ([el['ident']])
        el = db.Queue.pop ()
