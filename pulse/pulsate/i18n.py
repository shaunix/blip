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
import md5
import os
import os.path
import shutil

import pulse.config
import pulse.models as db
import pulse.scm
import pulse.parsers
import pulse.utils

from sqlobject.sqlbuilder import *

synop = 'update information about translations'
usage_extra = '[ident]'
args = pulse.utils.odict()
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

    potfile = get_intltool_potfile (po.parent, checkout, **kw)
    if potfile == None: return

    filepath = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
    if not os.path.exists (filepath):
        pulse.utils.warn('Could not locate file %s for %s' % (po.scm_file, po.parent.ident))
        return
    rel_scm = pulse.utils.relative_path (filepath, pulse.config.scm_dir)
    mtime = os.stat(filepath).st_mtime

    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pomd5 = po.data.get('md5', None)
            potmd5 = potfile.data.get('md5', None)
            if pomd5 != None and pomd5 == potmd5:
                pulse.utils.log ('Skipping file %s' % rel_scm)
                return

    podir = os.path.join (checkout.directory, po.scm_dir)
    cmd = 'msgmerge "%s" "%s" 2>&1' % (po.scm_file, potfile.get_file_path())
    owd = os.getcwd ()
    try:
        os.chdir (podir)
        pulse.utils.log ('Processing file ' + rel_scm)
        popo = pulse.parsers.Po (os.popen (cmd))
        stats = popo.get_stats()
        total = stats[0] + stats[1] + stats[2]
        db.Statistic.set_statistic (po, pulse.utils.daynum(), 'Messages',
                                    stats[0], stats[1], total)
    finally:
        os.chdir (owd)

    of = db.OutputFile.objects.filter (type='l10n', ident=po.parent.ident, filename=po.scm_file)
    try:
        of = of[0]
    except IndexError:
        of = db.OutputFile (type='l10n', ident=po.parent.ident, filename=po.scm_file,
                            datetime=datetime.datetime.now())
    outfile_abs = of.get_file_path()
    outfile_rel = pulse.utils.relative_path (outfile_abs, pulse.config.web_l10n_dir)
    outdir = os.path.dirname (outfile_abs)
    if not os.path.exists (outdir):
        os.makedirs (outdir)
    pulse.utils.log ('Copying PO file %s' % outfile_rel)
    shutil.copyfile (os.path.join (podir, po.scm_file), os.path.join (outdir, po.scm_file))
    of.datetime = datetime.datetime.now()
    of.data['revision'] = checkout.get_revision()
    of.save()

    files = [os.path.join (po.scm_dir, po.scm_file)]
    revision = db.Revision.get_last_revision (branch=po.parent.parent, files=files)
    if revision != None:
        po.mod_datetime = revision.datetime
        po.mod_person = revision.person

    # FIXME: things like .desktop files might not be reprocessed because
    # they haven't changed, but translators might have updated the name
    # or description.  Rather than trying to make those things run when
    # po files have been updated, let's just grab these:
    # po.parent.parent.select_children (...)
    # for Application, Capplet, Applet, and Library and see if we can
    # provide an updated name or description.

    po.data['md5'] = potfile.data.get('md5', None)
    po.save()
    db.Timestamp.set_timestamp (rel_scm, mtime)


def update_xml2po (po, **kw):
    checkout = kw.pop('checkout', None)
    if checkout == None:
        checkout = get_checkout (po, update=kw.get('update', True))

    potfile = get_xml2po_potfile (po.parent, checkout, **kw)
    if potfile == None: return

    filepath = os.path.join (checkout.directory, po.scm_dir, po.scm_file)
    if not os.path.exists (filepath):
        pulse.utils.warn('Could not locate file %s for %s' % (po.scm_file, po.parent.ident))
        return
    rel_scm = pulse.utils.relative_path (filepath, pulse.config.scm_dir)
    mtime = os.stat(filepath).st_mtime

    if kw.get('timestamps', True):
        stamp = db.Timestamp.get_timestamp (rel_scm)
        if mtime <= stamp:
            pomd5 = po.data.get('md5', None)
            potmd5 = potfile.data.get('md5', None)
            if pomd5 != None and pomd5 == potmd5:
                pulse.utils.log ('Skipping file %s' % rel_scm)
                return

    makedir = os.path.join (checkout.directory, os.path.dirname (po.scm_dir))
    cmd = 'msgmerge "%s" "%s" 2>&1' % (
        os.path.join (os.path.basename (po.scm_dir), po.scm_file),
        potfile.get_file_path() )
    owd = os.getcwd ()
    try:
        os.chdir (makedir)
        pulse.utils.log ('Processing file ' + rel_scm)
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

    po.data['figures'] = {}
    for figure in po.parent.data.get('figures', {}).keys():
        po.data['figures'].setdefault(figure, {})
        po.data['figures'][figure]['status'] = popo.get_image_status (figure)
        comment = po.parent.data['figures'][figure].get('comment', '')
        if comment == '':
            po.data['figures'][figure]['comment'] = ''
        elif popo.has_message (comment):
            po.data['figures'][figure]['comment'] = popo.get_translations (comment)[0]

    files = [os.path.join (po.scm_dir, po.scm_file)]
    revision = db.Revision.get_last_revision (branch=po.parent.parent, files=files)
    if revision != None:
        po.mod_datetime = revision.datetime
        po.mod_person = revision.person

    po.data['md5'] = potfile.data.get('md5', None)
    po.save()
    db.Timestamp.set_timestamp (rel_scm, mtime)
    

intltool_potfiles = {}
def get_intltool_potfile (domain, checkout, **kw):
    indir = os.path.join (checkout.directory, domain.scm_dir)
    if intltool_potfiles.has_key (indir):
        return intltool_potfiles[indir]

    if domain.scm_dir == 'po':
        potname = domain.scm_module
    else:
        potname = domain.scm_dir
    potfile = potname + '.pot'
    of = db.OutputFile.objects.filter (type='l10n', ident=domain.ident, filename=potfile)
    try:
        of = of[0]
    except IndexError:
        of = db.OutputFile (type='l10n', ident=domain.ident, filename=potfile,
                            datetime=datetime.datetime.now())

    potfile_abs = of.get_file_path()
    potfile_rel = pulse.utils.relative_path (potfile_abs, pulse.config.web_l10n_dir)

    if kw.get('timestamps', True):
        dt = of.data.get ('mod_datetime')
        if dt != None and dt == domain.parent.mod_datetime:
            pulse.utils.log ('Skipping POT file %s' % potfile_rel)
            intltool_potfiles[indir] = of
            return of

    potdir = os.path.dirname (potfile_abs)
    if not os.path.exists (potdir):
        os.makedirs (potdir)
    cmd = 'intltool-update -p -g "%s" && mv "%s" "%s"' % (potname, potfile, potdir)
    owd = os.getcwd ()
    try:
        os.chdir (indir)
        pulse.utils.log ('Creating POT file %s' % potfile_rel)
        (mstatus, moutput) = commands.getstatusoutput ('rm -f missing notexist && intltool-update -m')
        (status, output) = commands.getstatusoutput (cmd)
    finally:
        os.chdir (owd)
    missing = []
    if mstatus == 0:
        mfile = os.path.join (indir, 'missing')
        if os.access (mfile, os.R_OK):
            missing = [line.strip() for line in open(mfile).readlines()]
    if status == 0:
        m = md5.new()
        y = False
        popo = pulse.parsers.Po ()
        for line in open (potfile_abs):
            if y:
                m.update (line)
            if line.strip() == '':
                y = True
            popo.feed (line)
        popo.finish ()
        num = popo.get_num_messages ()
        of.datetime = datetime.datetime.now()
        of.data['mod_datetime'] = domain.parent.mod_datetime
        of.data['missing'] = missing
        of.statistic = num
        of.data['md5'] = m.hexdigest ()
        of.save()
        intltool_potfiles[indir] = of
        return of
    else:
        pulse.utils.warn('Failed to create POT file %s' % potfile_rel)
        intltool_potfiles[indir] = None
        return None


xml2po_potfiles = {}
def get_xml2po_potfile (doc, checkout, **kw):
    indir = os.path.dirname (os.path.join (checkout.directory, doc.scm_dir))
    if xml2po_potfiles.has_key (indir):
        return xml2po_potfiles[indir]

    makefile = pulse.parsers.Automake (os.path.join (indir, 'Makefile.am'))
    docfiles = [os.path.join ('C', fname)
                for fname in ([makefile['DOC_MODULE']+'.xml'] + makefile.get('DOC_INCLUDES', '').split())]
    potname = makefile['DOC_MODULE']
    potfile = potname + '.pot'
    of = db.OutputFile.objects.filter (type='l10n', ident=doc.ident, filename=potfile)
    try:
        of = of[0]
    except IndexError:
        of = db.OutputFile (type='l10n', ident=doc.ident, filename=potfile,
                            datetime=datetime.datetime.now())

    potfile_abs = of.get_file_path()
    potfile_rel = pulse.utils.relative_path (potfile_abs, pulse.config.web_l10n_dir)

    if kw.get('timestamps', True):
        dt = of.data.get ('mod_datetime')
        if dt != None and dt == doc.parent.mod_datetime:
            pulse.utils.log ('Skipping POT file %s' % potfile_rel)
            xml2po_potfiles[indir] = of
            return of

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
        m = md5.new()
        y = False
        popo = pulse.parsers.Po ()
        for line in open (potfile_abs):
            if y:
                m.update (line)
            if line.strip() == '':
                y = True
            popo.feed (line)
        popo.finish ()
        num = popo.get_num_messages ()
        of.datetime = datetime.datetime.now()
        of.data['mod_datetime'] = doc.parent.mod_datetime
        of.statistic = num
        of.data['md5'] = m.hexdigest ()
        of.save()
        xml2po_potfiles[indir] = of
        return of
    else:
        pulse.utils.warn ('Failed to create POT file %s' % potfile_rel)
        xml2po_potfiles[indir] = None
        return None
    

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
            update_intltool (po, update=update, timestamps=timestamps)
        elif po.subtype == 'xml2po':
            update_xml2po (po, update=update, timestamps=timestamps)
        else:
            pulse.utils.log ('Skipping translation %s with unknown type %s' %
                             (po.ident, po.subtype))
