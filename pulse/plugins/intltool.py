# Copyright (c) 2006-2009  Shaun McCance  <shaunm@gnome.org>
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
Plugins for intltool-managed translation .
"""

import commands
import datetime
import md5
import os
import shutil

from pulse import config, db, parsers, utils

import pulse.pulsate.i18n
import pulse.pulsate.modules

class PotModuleHandler (object):
    """
    ModuleScanner plugin for intltool-managed translation domains.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.podirs = []

    def process_file (self, dirname, basename, **kw):
        """
        Process a POTFILES.in file for intltool information.
        """
        if not basename == 'POTFILES.in':
            return

        branch = self.scanner.branch
        checkout = self.scanner.checkout
        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        ident = u'/'.join(['/i18n', bserver, bmodule, os.path.basename (dirname), bbranch])

        domain = db.Branch.get_or_create (ident, u'Domain')
        domain.parent = branch

        scmdata = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            scmdata[key] = getattr(branch, key)
        scmdata['scm_dir'] = utils.relative_path (dirname, checkout.directory)
        domain.update (scmdata)

        linguas = os.path.join (dirname, 'LINGUAS')
        if not os.path.isfile (linguas):
            domain.error = u'No LINGUAS file'
            return
        else:
            domain.error = None

        rel_scm = utils.relative_path (linguas, config.scm_dir)
        mtime = os.stat(linguas).st_mtime
        langs = []
        translations = []

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                return
        utils.log ('Processing file %s' % rel_scm)

        fd = open (linguas)
        for line in fd:
            if line.startswith ('#') or line == '\n':
                continue
            for lang in line.split():
                langs.append (lang)
        for lang in langs:
            lident = u'/l10n/' + lang + domain.ident
            translation = db.Branch.get_or_create (lident, u'Translation')
            translations.append (translation)
            ldata = {}
            for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                ldata[key] = scmdata[key]
            ldata['subtype'] = 'intltool'
            ldata['scm_dir'] = scmdata['scm_dir']
            ldata['scm_file'] = lang + '.po'
            translation.parent = domain
            translation.update (ldata)

        if not kw.get('no_i18n', False):
            for po in translations:
                pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

        db.Timestamp.set_timestamp (rel_scm, mtime)
        if domain is not None:
            self.scanner.add_child (domain)

pulse.pulsate.modules.ModuleScanner.register_plugin (PotModuleHandler)


class PotTranslationHandler (object):
    """
    TranslationScanner plugin for intltool-managed translations.
    """
    potfiles = {}

    def __init__ (self, scanner):
        self.scanner = scanner

    def update_translation (self, **kw):
        """
        Update information about an intltool-managed translation.
        """
        translation = self.scanner.translation
        checkout = self.scanner.checkout
        if translation.subtype != 'intltool':
            return False

        potfile = self.get_potfile (**kw)
        if potfile is None:
            return False

        filepath = os.path.join (checkout.directory,
                                 translation.scm_dir,
                                 translation.scm_file)
        if not os.path.exists (filepath):
            utils.warn('Could not locate file %s for %s'
                       % (translation.scm_file, translation.parent.ident))
            return False
        rel_scm = utils.relative_path (filepath, config.scm_dir)
        mtime = os.stat(filepath).st_mtime

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                pomd5 = translation.data.get('md5', None)
                potmd5 = potfile.data.get('md5', None)
                if pomd5 != None and pomd5 == potmd5:
                    utils.log ('Skipping file %s' % rel_scm)
                    return True

        podir = os.path.join (checkout.directory, translation.scm_dir)
        cmd = 'msgmerge "%s" "%s" 2>&1' % (translation.scm_file, potfile.get_file_path())
        owd = os.getcwd ()
        try:
            os.chdir (podir)
            pulse.utils.log ('Processing file ' + rel_scm)
            popo = parsers.Po (os.popen (cmd))
            stats = popo.get_stats()
            total = stats[0] + stats[1] + stats[2]
            db.Statistic.set_statistic (translation, utils.daynum(), u'Messages',
                                        stats[0], stats[1], total)
        finally:
            os.chdir (owd)

        # FIXME: things like .desktop files might not be reprocessed because
        # they haven't changed, but translators might have updated the name
        # or description.  Rather than trying to make those things run when
        # po files have been updated, let's just grab these:
        # po.parent.parent.select_children (...)
        # for Application, Capplet, Applet, and Library and see if we can
        # provide an updated name or description.

        of = db.OutputFile.select (type=u'l10n',
                                   ident=translation.parent.ident,
                                   filename=translation.scm_file)
        try:
            of = of[0]
        except IndexError:
            of = db.OutputFile (type=u'l10n',
                                ident=translation.parent.ident,
                                filename=translation.scm_file,
                                datetime=datetime.datetime.utcnow())
        outfile_abs = of.get_file_path()
        outfile_rel = pulse.utils.relative_path (outfile_abs, config.web_l10n_dir)
        outdir = os.path.dirname (outfile_abs)
        if not os.path.exists (outdir):
            os.makedirs (outdir)
        utils.log ('Copying PO file %s' % outfile_rel)
        shutil.copyfile (os.path.join (checkout.directory,
                                       translation.scm_dir,
                                       translation.scm_file),
                         os.path.join (outdir, translation.scm_file))
        of.datetime = datetime.datetime.utcnow()
        of.data['revision'] = checkout.get_revision()

        files = [os.path.join (translation.scm_dir, translation.scm_file)]
        revision = db.Revision.get_last_revision (branch=translation.parent.parent, files=files)
        if revision != None:
            translation.mod_datetime = revision.datetime
            translation.mod_person = revision.person

        translation.data['md5'] = potfile.data.get('md5', None)
        db.Timestamp.set_timestamp (rel_scm, mtime)

        return True


    def get_potfile (self, **kw):
        """
        Get a POT file for an intltool-managed translation domain.
        """
        checkout = self.scanner.checkout
        domain = self.scanner.translation.parent
        indir = os.path.join (checkout.directory, domain.scm_dir)
        if self.__class__.potfiles.has_key (indir):
            return self.__class__.potfiles[indir]

        if domain.scm_dir == 'po':
            potname = domain.scm_module
        else:
            potname = domain.scm_dir
        potfile = potname + '.pot'
        of = pulse.db.OutputFile.select (type=u'l10n', ident=domain.ident, filename=potfile)
        try:
            of = of[0]
        except IndexError:
            of = pulse.db.OutputFile (type=u'l10n', ident=domain.ident, filename=potfile,
                                      datetime=datetime.datetime.utcnow())

        potfile_abs = of.get_file_path()
        potfile_rel = utils.relative_path (potfile_abs, config.web_l10n_dir)

        if not kw.get('no_timestamps', False):
            dt = of.data.get ('mod_datetime')
            if dt != None and dt == domain.parent.mod_datetime:
                pulse.utils.log ('Skipping POT file %s' % potfile_rel)
                self.__class__.potfiles[indir] = of
                return of

        potdir = os.path.dirname (potfile_abs)
        if not os.path.exists (potdir):
            os.makedirs (potdir)
        cmd = 'intltool-update -p -g "%s" && mv "%s" "%s"' % (potname, potfile, potdir)
        owd = os.getcwd ()
        try:
            os.chdir (indir)
            pulse.utils.log ('Creating POT file %s' % potfile_rel)
            (mstatus, moutput) = commands.getstatusoutput (
                'rm -f missing notexist && intltool-update -m')
            (status, output) = commands.getstatusoutput (cmd)
        finally:
            os.chdir (owd)
        missing = []
        if mstatus == 0:
            mfile = os.path.join (indir, 'missing')
            if os.access (mfile, os.R_OK):
                missing = [line.strip() for line in open(mfile).readlines()]
        if status == 0:
            potmd5 = md5.new()
            # We don't start feeding potmd5 until we've hit a blank line.
            # This keeps inconsequential differences in the header from
            # affecting the MD5.
            blankline = False
            popo = parsers.Po ()
            for line in open (potfile_abs):
                if blankline:
                    potmd5.update (line)
                elif line.strip() == '':
                    blankline = True
                popo.feed (line)
            popo.finish ()
            num = popo.get_num_messages ()
            of.datetime = datetime.datetime.utcnow()
            of.data['mod_datetime'] = domain.parent.mod_datetime
            of.data['missing'] = missing
            of.statistic = num
            of.data['md5'] = potmd5.hexdigest ()
            self.__class__.potfiles[indir] = of
            domain.error = None
            domain.updated = of.datetime
            return of
        else:
            domain.error = u'Failed to create POT file'
            pulse.utils.warn('Failed to create POT file %s' % potfile_rel)
            self.__class__.potfiles[indir] = None
            return None

pulse.pulsate.i18n.TranslationScanner.register_plugin (PotTranslationHandler)
