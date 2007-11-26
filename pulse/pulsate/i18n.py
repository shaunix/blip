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
import pulse.db
import pulse.scm
import pulse.parsers
import pulse.utils

from sqlobject.sqlbuilder import *

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
    potfile = get_intltool_potfile (po, checkout)
    if potfile == None: return
    podir = os.path.join (checkout.directory, po.scm_dir)
    cmd = 'msgmerge "' + po.scm_file + '" "' + potfile + '" 2>&1'
    owd = os.getcwd ()
    try:
        os.chdir (podir)
        filepath = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
        pulse.utils.log ('Processing file ' + pulse.utils.relative_path (filepath, pulse.config.scmdir))
        popo = pulse.parsers.Po (os.popen (cmd))
        stats = popo.get_stats()
        total = stats[0] + stats[1] + stats[2]
        pulse.db.Statistic.set_statistic (po, pulse.utils.daynum(), 'Messages',
                                          stats[0], stats[1], total)
    finally:
        os.chdir (owd)
    do_history (po, checkout, timestamps=timestamps)


def update_xml2po (po, update=True, timestamps=True):
    checkout = get_checkout (po.parent.parent, update=update)
    potfile = get_xml2po_potfile (po, checkout)
    if potfile == None: return
    makedir = os.path.join (checkout.directory, os.path.dirname (po.scm_dir))
    cmd = 'msgmerge "' + os.path.join (os.path.basename (po.scm_dir), po.scm_file) + '" "' + potfile + '" 2>&1'
    owd = os.getcwd ()
    try:
        os.chdir (makedir)
        filepath = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
        pulse.utils.log ('Processing file ' + pulse.utils.relative_path (filepath, pulse.config.scmdir))
        popo = pulse.parsers.Po (os.popen (cmd))
        stats = popo.get_stats()
        total = stats[0] + stats[1] + stats[2]
        pulse.db.Statistic.set_statistic (po, pulse.utils.daynum(), 'Messages',
                                          stats[0], stats[1], total)
        stats = popo.get_image_stats()
        total = stats[0] + stats[1] + stats[2]
        pulse.db.Statistic.set_statistic (po, pulse.utils.daynum(), 'ImageMessages',
                                          stats[0], stats[1], total)
    finally:
        os.chdir (owd)
    do_history (po, checkout, timestamps=timestamps)
    

intltool_potfiles = {}
def get_intltool_potfile (po, checkout):
    podir = os.path.join (checkout.directory, po.scm_dir)
    if intltool_potfiles.has_key (podir):
        return intltool_potfiles[podir]
    potdir_rel = os.path.join (*(['var', 'l10n'] + po.ident.split('/')[3:]))
    potdir_abs = os.path.join (pulse.config.webdir, potdir_rel)
    if po.scm_dir == 'po':
        potname = po.parent.parent.scm_module
    else:
        potname = po.scm_dir
    potfile = potname + '.pot'
    potfile_rel = os.path.join (potdir_rel, potfile)
    potfile_abs = os.path.join (potdir_abs, potfile)
    if not os.path.exists (potdir_abs):
        os.makedirs (potdir_abs)
    cmd = 'intltool-update -p -g "%s" && mv "%s" "%s"' % (potname, potfile, potdir_abs)
    owd = os.getcwd ()
    try:
        os.chdir (podir)
        pulse.utils.log ('Creating POT file %s' % potfile_rel)
        (status, output) = commands.getstatusoutput (cmd)
    finally:
        os.chdir (owd)
    if status == 0:
        popo = pulse.parsers.Po (potfile_abs)
        num = popo.get_num_messages ()
        vf = pulse.db.VarFile.selectBy (filename=potfile_rel)
        try:
            vf = vf[0]
            vf.set(datetime=datetime.datetime.now(), statistic=num)
        except IndexError:
            pulse.db.VarFile (filename=potfile_rel, datetime=datetime.datetime.now(), statistic=num)
        intltool_potfiles[podir] = potfile_abs
        return potfile_abs
    else:
        pulse.utils.warn ('Failed to create POT file %s' % potfile_rel)
        intltool_potfiles[podir] = None
        return None


xml2po_potfiles = {}
def get_xml2po_potfile (po, checkout):
    makedir = os.path.join (checkout.directory, os.path.dirname (po.scm_dir))
    if xml2po_potfiles.has_key (makedir):
        return xml2po_potfiles[makedir]
    makefile = pulse.parsers.Automake (os.path.join (makedir, 'Makefile.am'))
    docfiles = [os.path.join ('C', fname)
                for fname in ([makefile['DOC_MODULE']+'.xml'] + makefile.get('DOC_INCLUDES', '').split())]
    potdir_rel = os.path.join (*(['var', 'l10n'] + po.ident.split('/')[3:]))
    potdir_abs = os.path.join (pulse.config.webdir, potdir_rel)
    potfile_rel = os.path.join (potdir_rel, makefile['DOC_MODULE'] + '.pot')
    potfile_abs = os.path.join (potdir_abs, makefile['DOC_MODULE'] + '.pot')
    if not os.path.exists (potdir_abs):
        os.makedirs (potdir_abs)
    cmd = 'xml2po -e -o "' + potfile_abs + '" "' + '" "'.join(docfiles) + '"'
    owd = os.getcwd ()
    try:
        os.chdir (makedir)
        pulse.utils.log ('Creating POT file %s' % potfile_rel)
        (status, output) = commands.getstatusoutput (cmd)
    finally:
        os.chdir (owd)
    if status == 0:
        popo = pulse.parsers.Po (potfile_abs)
        num = popo.get_num_messages ()
        vf = pulse.db.VarFile.selectBy (filename=potfile_rel)
        try:
            vf = vf[0]
            vf.set(datetime=datetime.datetime.now(), statistic=num)
        except IndexError:
            pulse.db.VarFile (filename=potfile_rel, datetime=datetime.datetime.now(), statistic=num)
        xml2po_potfiles[makedir] = potfile_abs
        return potfile_abs
    else:
        pulse.utils.warn ('Failed to create POT file %s' % potfile_rel)
        xml2po_potfiles[makedir] = None
        return None
    

def do_history (po, checkout, **kw):
    fullname = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
    rel_ch = pulse.utils.relative_path (fullname, checkout.directory)
    rel_scm = pulse.utils.relative_path (fullname, pulse.config.scmdir)
    mtime = os.stat(fullname).st_mtime
    if kw.get('timestamps', True):
        stamp = pulse.db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pulse.utils.warn ('Skipping history for %s' % rel_scm)
            return
    pulse.utils.log ('Checking history for %s' % rel_scm)
    revision = pulse.db.Revision.select ((pulse.db.Revision.q.branchID == po.id) &
                                         (pulse.db.Revision.q.filename == po.scm_file),
                                         orderBy='-datetime')
    try:
        since = revision[0].revision
    except IndexError:
        since = None
    serverid = '.'.join (pulse.scm.server_name (checkout.scm_type, checkout.scm_server).split('.')[-2:])
    for hist in checkout.get_history (rel_ch, since=since):
        pident = '/person/' + serverid + '/' + hist['userid']
        pers = pulse.db.Entity.get_record (ident=pident, type='Person')
        pulse.db.Revision (branch=po, person=pers, filename=po.scm_file, filetype='po',
                           revision=hist['revision'], datetime=hist['date'], comment=hist['comment'])
    pulse.db.Timestamp.set_timestamp (rel_scm, mtime)
    


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
        BranchParent = Alias (pulse.db.Branch, 'BranchParent')
        pos = pulse.db.Branch.select (
            AND(pulse.db.Branch.q.type == 'Translation',
                BranchParent.q.type == 'Domain',
                BranchParent.q.ident.startswith (prefix)),
            join=INNERJOINOn(None, BranchParent,
                             pulse.db.Branch.q.parentID == BranchParent.q.id) )
        pos = list(pos)
    elif prefix.startswith ('/doc/') or prefix.startswith ('/ref/'):
        BranchParent = Alias (pulse.db.Branch, 'BranchParent')
        pos = pulse.db.Branch.select (
            AND(pulse.db.Branch.q.type == 'Translation',
                BranchParent.q.type == 'Document',
                BranchParent.q.ident.startswith (prefix)),
            join=INNERJOINOn(None, BranchParent,
                             pulse.db.Branch.q.parentID == BranchParent.q.id) )
        pos = list(pos)
    elif prefix.startswith ('/mod'):
        BranchParent = Alias (pulse.db.Branch, 'BranchParent')
        BranchGrand = Alias (pulse.db.Branch, 'BranchGrand')
        pos = pulse.db.Branch.select (
            AND(pulse.db.Branch.q.type == 'Translation',
                BranchGrand.q.type == 'Module',
                BranchGrand.q.ident.startswith (prefix)),
            join=INNERJOINOn(BranchParent, BranchGrand,
                             AND(pulse.db.Branch.q.parentID == BranchParent.q.id,
                                 BranchParent.q.parentID == BranchGrand.q.id)) )
        pos = list(pos)
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
