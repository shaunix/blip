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
import datetime
import os
import os.path

import pulse.config
import pulse.models as db
import pulse.scm
import pulse.parsers
import pulse.utils

from sqlobject.sqlbuilder import *

synop = 'update information about translations'
usage_extra = '[ident]'
args = pulse.utils.odict()
args['no-history'] = (None, 'do not check SCM history')
args['no-timestamps'] = (None, 'do not check timestamps before processing files')
args['no-update']  = (None, 'do not update SCM checkouts')
def help_extra (fd=None):
    print >>fd, 'If ident is passed, only translations with a matching identifier will be updated.'


checkouts = {}
def get_checkout (record, update=True):
    key = '::'.join(map(str, [record.scm_type, record.scm_server, record.scm_module, record.scm_branch, record.scm_path]))
    if not checkouts.has_key (key):
        checkouts[key] = pulse.scm.Checkout.from_record (record, update=update)
    return checkouts[key]


def update_intltool (po, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (po, update=kw.get('update', True))
    potfile = get_intltool_potfile (po, checkout)
    if potfile == None: return
    podir = os.path.join (checkout.directory, po.scm_dir)
    cmd = 'msgmerge "' + po.scm_file + '" "' + potfile + '" 2>&1'
    owd = os.getcwd ()
    try:
        os.chdir (podir)
        filepath = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
        pulse.utils.log ('Processing file ' + pulse.utils.relative_path (filepath, pulse.config.scm_dir))
        popo = pulse.parsers.Po (os.popen (cmd))
        stats = popo.get_stats()
        total = stats[0] + stats[1] + stats[2]
        db.Statistic.set_statistic (po, pulse.utils.daynum(), 'Messages',
                                    stats[0], stats[1], total)
    finally:
        os.chdir (owd)
    if kw.get('history', True):
        do_history (po, checkout, **kw)


def update_xml2po (po, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (po, update=kw.get('update', True))
    potfile = get_xml2po_potfile (po, checkout)
    if potfile == None: return
    makedir = os.path.join (checkout.directory, os.path.dirname (po.scm_dir))
    cmd = 'msgmerge "' + os.path.join (os.path.basename (po.scm_dir), po.scm_file) + '" "' + potfile + '" 2>&1'
    owd = os.getcwd ()
    try:
        os.chdir (makedir)
        filepath = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
        pulse.utils.log ('Processing file ' + pulse.utils.relative_path (filepath, pulse.config.scm_dir))
        popo = pulse.parsers.Po (os.popen (cmd))
        stats = popo.get_stats()
        total = stats[0] + stats[1] + stats[2]
        db.Statistic.set_statistic (po, pulse.utils.daynum(), 'Messages',
                                    stats[0], stats[1], total)
        stats = popo.get_image_stats()
        total = stats[0] + stats[1] + stats[2]
        db.Statistic.set_statistic (po, pulse.utils.daynum(), 'ImageMessages',
                                    stats[0], stats[1], total)
    finally:
        os.chdir (owd)
    if kw.get('history', True):
        do_history (po, checkout, **kw)
    

intltool_potfiles = {}
def get_intltool_potfile (po, checkout):
    indir = os.path.join (checkout.directory, po.scm_dir)
    if intltool_potfiles.has_key (indir):
        return intltool_potfiles[indir]

    if po.scm_dir == 'po':
        potname = po.scm_module
    else:
        potname = po.scm_dir
    potfile = potname + '.pot'
    of = db.OutputFile.objects.filter (type='l10n', ident=po.parent.ident, filename=potfile)
    try:
        of = of[0]
        of.datetime = datetime.datetime.now()
    except IndexError:
        of = db.OutputFile (type='l10n', ident=po.parent.ident, filename=potfile,
                            datetime=datetime.datetime.now())

    potfile_abs = of.get_file_path()
    potfile_rel = pulse.utils.relative_path (potfile_abs, pulse.config.web_l10n_dir)
    potdir = os.path.dirname (potfile_abs)
    if not os.path.exists (potdir):
        os.makedirs (potdir)
    cmd = 'intltool-update -p -g "%s" && mv "%s" "%s"' % (potname, potfile, potdir)
    owd = os.getcwd ()
    try:
        os.chdir (indir)
        pulse.utils.log ('Creating POT file %s' % potfile_rel)
        (status, output) = commands.getstatusoutput (cmd)
    finally:
        os.chdir (owd)
    if status == 0:
        popo = pulse.parsers.Po (potfile_abs)
        num = popo.get_num_messages ()
        of.datetime = datetime.datetime.now()
        of.statistic = num
        of.save()
        intltool_potfiles[indir] = potfile_abs
        return potfile_abs
    else:
        pulse.utils.warn ('Failed to create POT file %s' % potfile_rel)
        intltool_potfiles[indir] = None
        return None


xml2po_potfiles = {}
def get_xml2po_potfile (po, checkout):
    indir = os.path.dirname (os.path.join (checkout.directory, po.scm_dir))
    if xml2po_potfiles.has_key (indir):
        return xml2po_potfiles[indir]

    makefile = pulse.parsers.Automake (os.path.join (indir, 'Makefile.am'))
    docfiles = [os.path.join ('C', fname)
                for fname in ([makefile['DOC_MODULE']+'.xml'] + makefile.get('DOC_INCLUDES', '').split())]
    potname = makefile['DOC_MODULE']
    potfile = potname + '.pot'
    of = db.OutputFile.objects.filter (type='l10n', ident=po.parent.ident, filename=potfile)
    try:
        of = of[0]
        of.datetime = datetime.datetime.now()
    except IndexError:
        of = db.OutputFile (type='l10n', ident=po.parent.ident, filename=potfile,
                            datetime=datetime.datetime.now())

    potfile_abs = of.get_file_path()
    potfile_rel = pulse.utils.relative_path (potfile_abs, pulse.config.web_l10n_dir)
    potdir = os.path.dirname (potfile_abs)
    if not os.path.exists (potdir):
        os.makedirs (potdir)

    cmd = 'xml2po -e -o "' + potfile_abs + '" "' + '" "'.join(docfiles) + '"'
    owd = os.getcwd ()
    try:
        os.chdir (indir)
        pulse.utils.log ('Creating POT file %s' % potfile_rel)
        (status, output) = commands.getstatusoutput (cmd)
    finally:
        os.chdir (owd)
    if status == 0:
        popo = pulse.parsers.Po (potfile_abs)
        num = popo.get_num_messages ()
        of.datetime = datetime.datetime.now()
        of.statistic = num
        of.save()
        xml2po_potfiles[indir] = potfile_abs
        return potfile_abs
    else:
        pulse.utils.warn ('Failed to create POT file %s' % potfile_rel)
        xml2po_potfiles[indir] = None
        return None
    

def do_history (po, checkout, **kw):
    fullname = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
    rel_ch = pulse.utils.relative_path (fullname, checkout.directory)
    rel_scm = pulse.utils.relative_path (fullname, pulse.config.scm_dir)
    mtime = os.stat(fullname).st_mtime
    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.warn ('Skipping history for %s' % rel_scm)
            return
    pulse.utils.log ('Checking history for %s' % rel_scm)
    since = db.Revision.get_last_revision (branch=po, filename=po.scm_file)
    if since != None:
        since = since.revision
    serverid = '.'.join (pulse.scm.server_name (checkout.scm_type, checkout.scm_server).split('.')[-2:])
    for hist in checkout.get_file_history (rel_ch, since=since):
        pident = '/person/' + serverid + '/' + hist['userid']
        pers = db.Entity.get_record (pident, 'Person')
        rev = db.Revision (branch=po, person=pers, filename=po.scm_file, filetype='po',
                           revision=hist['revision'], datetime=hist['date'], comment=hist['comment'])
        rev.save()
    db.Timestamp.set_timestamp (rel_scm, mtime)
    


################################################################################
## main

def main (argv, options={}):
    update = not options.get ('--no-update', False)
    timestamps = not options.get ('--no-timestamps', False)
    history = not options.get ('--no-history', False)
    if len(argv) == 0:
        prefix = None
    else:
        prefix = argv[0]

    if prefix == None:
        pos = db.Branch.objects.filter (type='Translation')
    elif prefix.startswith ('/set/'):
        pos = db.Branch.objects.filter (type='Translation',
                                        parent__parent__set_module_subjs__subj__ident__startswith=prefix)
    elif prefix.startswith ('/i18n/'):
        pos = db.Branch.objects.filter (type='Translation',
                                        parent__ident__startswith=prefix)
    elif prefix.startswith ('/doc/') or prefix.startswith ('/ref/'):
        pos = db.Branch.objects.filter (type='Translation',
                                        parent__ident__startswith=prefix)
    elif prefix.startswith ('/mod'):
        pos = db.Branch.objects.filter (type='Translation',
                                        parent__parent__ident__startswith=prefix)
    else:
        pos = db.Branch.objects.filter (type='Translation',
                                        ident__startswith=prefix)

    for po in list(pos):
        if po.subtype == 'intltool':
            update_intltool (po, update=update, timestamps=timestamps, history=history)
        elif po.subtype == 'xml2po':
            update_xml2po (po, update=update, timestamps=timestamps, history=history)
        else:
            pulse.utils.log ('Skipping translation %s with unknown type %s' %
                             (po.ident, po.subtype))
