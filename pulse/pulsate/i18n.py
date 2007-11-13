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

import commands
import os
import os.path

import pulse.db
import pulse.scm
import pulse.parsers
import pulse.utils

synop = 'update information about translations'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-update']  = (None, 'do not update SCM checkouts')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only translations with a matching identifier will be updated.'


checkouts = {}
def get_checkout (branch, update=True):
    if not checkouts.has_key (branch.ident):
        checkouts[branch.ident] = pulse.scm.Checkout.from_record (branch, update=update)
    return checkouts[branch.ident]


def update_intltool (po, update=True, timestamps=True):
    checkout = get_checkout (po.parent.parent, update=update)
    podir = os.path.join (checkout.directory, po.scm_dir)
    tmpfile = po.scm_file + '.pulse-tmp-file'
    cmd = 'intltool-update %s -o %s 2>&1' % (po.scm_file[:-3], tmpfile)
    owd = os.getcwd ()
    stats = [0, 0, 0]
    try:
        os.chdir (podir)
        for line in os.popen (cmd):
            if line.startswith ('.'): continue
            line = line.strip()
            if line.endswith ('.'):
                line = line[:-1]
            for field in line.split(','):
                field = field.strip()
                if field.endswith (' translated messages'):
                    stats[0] = int(field.split()[0])
                elif field.endswith (' fuzzy translations'):
                    stats[1] = int(field.split()[0])
                elif field.endswith (' untranslated messages'):
                    stats[2] = int(field.split()[0])
        total = stats[0] + stats[1] + stats[2]
        pulse.db.Statistic.set_statistic (po, pulse.utils.daynum(), 'Messages',
                                          stats[0], stats[1], total)
        if os.path.exists (tmpfile): os.remove (tmpfile)
    finally:
        os.chdir (owd)


def update_xml2po (po, update=True, timestamps=True):
    pass


################################################################################
## main

def main (argv, options={}):
    update = not options.get ('--no-update', False)
    timestamps = not options.get ('--no-timestamps', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix == None:
        pos = pulse.db.Branch.selectBy (type='Translation')
    elif prefix.startswith ('/i18n/'):
        domains = pulse.db.Branch.select ((pulse.db.Branch.q.type == 'Domain') &
                                          (pulse.db.Branch.q.ident.startswith (prefix)) )
        pos = []
        for domain in domains:
            pos += list(pulse.db.Branch.selectBy (type='Translation', parent=domain))
    # FIXME: an elif for document translations
    else:
        pos = pulse.db.Branch.select ((pulse.db.Branch.q.type == 'Translation') &
                                      (pulse.db.Branch.q.ident.startswith (prefix)) )

    for po in pos:
        if po.subtype == 'intltool':
            update_intltool (po, update=update, timestamps=timestamps)
        elif po.subtype == 'xml2po':
            update_xml2po (po, update=update, timestamps=timestamps)
        else:
            pulse.utils.log ('Skipping translation %s with unknown type %s' %
                             (po.ident, po.subtype))
