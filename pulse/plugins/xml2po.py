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
Plugins for xml2po-managed translation .
"""

import commands
import datetime
import md5
import os
import shutil

from pulse import config, db, parsers, utils

import pulse.pulsate.i18n

class Xml2PoTranslationHandler (object):
    """
    TranslationScanner plugin for xml2po-managed translations.
    """
    potfiles = {}
    def __init__ (self, scanner):
        self.scanner = scanner

    def update_translation (self, **kw):
        """
        Update information about an xml2po-managed translation.
        """
        translation = self.scanner.translation
        checkout = self.scanner.checkout
        if translation.subtype != 'xml2po':
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

        makedir = os.path.join (checkout.directory,
                                os.path.dirname (translation.scm_dir))
        cmd = 'msgmerge "%s" "%s" 2>&1' % (
            os.path.join (os.path.basename (translation.scm_dir), translation.scm_file),
            potfile.get_file_path() )
        owd = os.getcwd ()
        try:
            os.chdir (makedir)
            utils.log ('Processing file ' + rel_scm)
            popo = pulse.parsers.Po (os.popen (cmd))
            stats = popo.get_stats()
            total = stats[0] + stats[1] + stats[2]
            db.Statistic.set_statistic (translation, utils.daynum(), u'Messages',
                                        stats[0], stats[1], total)
            stats = popo.get_image_stats()
            total = stats[0] + stats[1] + stats[2]
            db.Statistic.set_statistic (translation, utils.daynum(), u'ImageMessages',
                                        stats[0], stats[1], total)
        finally:
            os.chdir (owd)

        translation.data['figures'] = {}
        for figure in translation.parent.data.get('figures', {}).keys():
            translation.data['figures'].setdefault(figure, {})
            translation.data['figures'][figure]['status'] = popo.get_image_status (figure)
            comment = translation.parent.data['figures'][figure].get('comment', '')
            if comment == '':
                translation.data['figures'][figure]['comment'] = ''
            elif popo.has_message (comment):
                translation.data['figures'][figure]['comment'] = popo.get_translations (comment)[0]

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
        Get a POT file for an xml2po-managed translation domain.
        """
        checkout = self.scanner.checkout
        domain = self.scanner.translation.parent
        indir = os.path.dirname (os.path.join (checkout.directory, domain.scm_dir))
        if self.__class__.potfiles.has_key (indir):
            return self.__class__.potfiles[indir]

        makefile = parsers.Automake (os.path.join (indir, 'Makefile.am'))
        doc_module = makefile['DOC_MODULE']
        if doc_module == '@PACKAGE_NAME@':
            doc_module = domain.parent.data.get ('PACKAGE_NAME', '@PACKAGE_NAME@')
        docfiles = [os.path.join ('C', fname)
                    for fname
                    in ([doc_module+'.xml'] + makefile.get('DOC_INCLUDES', '').split())]
        potname = doc_module
        potfile = potname + u'.pot'
        of = db.OutputFile.select (type=u'l10n', ident=domain.ident, filename=potfile)
        try:
            of = of[0]
        except IndexError:
            of = db.OutputFile (type=u'l10n', ident=domain.ident, filename=potfile,
                                datetime=datetime.datetime.utcnow())

        potfile_abs = of.get_file_path()
        potfile_rel = utils.relative_path (potfile_abs, config.web_l10n_dir)

        if not kw.get('no_timestamps', False):
            dt = of.data.get ('mod_datetime')
            if dt != None and dt == domain.parent.mod_datetime:
                utils.log ('Skipping POT file %s' % potfile_rel)
                self.__class__.potfiles[indir] = of
                return of

        potdir = os.path.dirname (potfile_abs)
        if not os.path.exists (potdir):
            os.makedirs (potdir)

        cmd = 'xml2po -e -o "' + potfile_abs + '" "' + '" "'.join(docfiles) + '"'
        owd = os.getcwd ()
        try:
            os.chdir (indir)
            utils.log ('Creating POT file %s' % potfile_rel)
            (status, output) = commands.getstatusoutput (cmd)
        finally:
            os.chdir (owd)
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
            of.statistic = num
            of.data['md5'] = potmd5.hexdigest ()
            self.__class__.potfiles[indir] = of
            return of
        else:
            utils.warn ('Failed to create POT file %s' % potfile_rel)
            self.__class__.potfiles[indir] = None
            return None

pulse.pulsate.i18n.TranslationScanner.register_plugin (Xml2PoTranslationHandler)
