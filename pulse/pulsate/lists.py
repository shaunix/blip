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

import pulse.models as db
import pulse.xmldata

synop = 'update information about mailing lists'
args = pulse.utils.odict()
args['shallow'] = (None, 'only update information from the XML input file')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')

def update_lists (**kw):
    queue = []
    data = pulse.xmldata.get_data (os.path.join (pulse.config.input_dir, 'xml', 'lists.xml'))

    for key in data.keys():
        if not data[key]['__type__'] == 'list':
            continue
        if not (data[key].has_key ('id') and data[key].has_key ('ident')):
            continue
        mlist = db.Forum.get_record (data[key]['ident'], 'List')

        for k in ('name', 'email', 'list_id', 'list_info', 'list_archive'):
            if data[key].has_key (k):
                mlist.update(**{k : data[key][k]})

        mlist.save()

    return queue


def update_list (mlist, **kw):
    pass


def main (argv, options={}):
    shallow = options.get ('--shallow', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    queue = update_lists (timestamps=timestamps, shallow=shallow)

    if not shallow:
        for mlist in queue:
            update_list (mlist, timestamps=timestamps, shallow=shallow)
        if prefix == None:
            mlists = db.Forum.objects.filter (type='List')
        else:
            mlists = db.Forum.objects.filter (type='List', ident__startswith=prefix)
        for mlist in mlists:
            update_list (mlist, timestamps=timestamps, shallow=shallow)
    else:
        for mlist in queue:
            db.Queue.push ('lists', mlist.ident)
