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
Plugins for the Evolution Quick Reference Card.
"""

import datetime
import Image
import os
import re
import StringIO

from pulse import db, parsers, utils

import pulse.pulsate.i18n
import pulse.pulsate.modules

class EvolutionQuickRefModuleHandler (object):
    """
    ModuleScanner plugin for the Evolution Quick Reference Card.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def process_file (self, dirname, basename, **kw):
        """
        Process a Makefile.am file for the Evolution Quick Reference Card.
        """
        branch = self.scanner.branch
        checkout = self.scanner.checkout
        is_quickref = False
        if branch.scm_server == 'http://svn.gnome.org/svn/' and branch.scm_module == 'evolution':
            if basename == 'Makefile.am':
                if os.path.join (checkout.directory, 'help/quickref') == dirname:
                    is_quickref = True
        if not is_quickref:
            return

        filename = os.path.join (dirname, basename)
        makefile = self.scanner.get_parsed_file (parsers.Automake, filename)

        bserver, bmodule, bbranch = branch.ident.split('/')[2:]

        ident = u'/'.join(['/doc', bserver, bmodule, u'quickref', bbranch])
        document = db.Branch.get_or_create (ident, u'Document')
        document.parent = branch

        relpath = utils.relative_path (dirname, checkout.directory)

        data = {}
        for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
            data[key] = getattr(branch, key)
        data['subtype'] = u'evolution-quickref'
        data['scm_dir'] = os.path.join (relpath, 'C')
        data['scm_file'] = u'quickref.tex'
        document.update (data)

        langs = makefile['SUBDIRS'].split ()
        translations = []
        for lang in langs:
            if lang == 'C':
                continue
            lident = u'/l10n/' + lang + document.ident
            translation = db.Branch.get_or_create (lident, u'Translation')
            translations.append (translation)
            ldata = {}
            for key in ('scm_type', 'scm_server', 'scm_module', 'scm_branch', 'scm_path'):
                ldata[key] = data[key]
            ldata['subtype'] = u'evolution-quickref'
            ldata['scm_dir'] = os.path.join (
                utils.relative_path (dirname, checkout.directory),
                lang)
            ldata['scm_file'] = u'quickref.tex'
            translation.parent = document
            translation.update (ldata)
        document.set_children (u'Translation', translations)

        if not kw.get('no_i18n', False):
            for po in translations:
                pulse.pulsate.i18n.update_translation (po, checkout=checkout, **kw)

        if not kw.get('no_docs', False):
            pulse.pulsate.docs.update_document (document, checkout=checkout, **kw)

        if document is not None:
            self.scanner.add_child (document)

pulse.pulsate.modules.ModuleScanner.register_plugin (EvolutionQuickRefModuleHandler)


class EvolutionQuickRefDocumentHandler (object):
    """
    DocumentScanner plugin for the Evolution Quick Reference Card.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def update_document (self, **kw):
        document = self.scanner.document
        checkout = self.scanner.checkout
        if document.subtype != u'evolution-quickref':
            return False

        langs = [('C', document)]
        translations = db.Branch.select (type=u'Translation', parent=document)
        for translation in translations:
            langs.append ((os.path.basename (translation.scm_dir), translation))

        name = {}
        regexp = re.compile ('\\s*\\\\textbf{\\\\Huge{(.*)}}')

        ofs_by_lang = {}
        ofs = list(db.OutputFile.select (type=u'figures', ident=document.ident))
        for of in ofs:
            ofs_by_lang[of.filename[:-4]] = of

        for lang, obj in langs:
            texfile = os.path.join (checkout.directory, obj.scm_dir, obj.scm_file)
            for line in open (texfile):
                match = regexp.match (line)
                if match:
                    name[lang] = match.group (1)
                    break
                
            of = ofs_by_lang.get (lang, None)
            create_figure = False
            pdffile = os.path.join (obj.scm_dir, 'quickref.pdf')
            pdffull = os.path.join (checkout.directory, pdffile)
            if of is None:
                of = db.OutputFile (type=u'figures', ident=document.ident,
                                    filename=(lang + u'.png'), source=pdffile,
                                    datetime=datetime.datetime.utcnow())
                create_figure = True
            else:
                if kw.get('no_timestamps', False):
                    create_figure = True
                else:
                    try:
                        mtime = os.stat(pdffull).st_mtime
                        if mtime > time.mktime(of.datetime.timetuple()):
                            create_figure = True
                    except:
                        pass
            outfile = of.get_file_path ()
            outfile_rel = utils.relative_path (outfile, pulse.config.web_figures_dir)
            if create_figure:
                outdir = os.path.dirname (outfile)
                if not os.path.exists (outdir):
                    os.makedirs (outdir)
                utils.log ('Creating image %s' % outfile_rel)
                try:
                    fd = os.popen ('convert "%s" png:-' % pdffull)
                    im = Image.open (StringIO.StringIO (fd.read()))
                    im = im.rotate (-90)
                    im.thumbnail ((600, 600), Image.ANTIALIAS)

                    width, height = im.size
                    im.save (outfile)

                    tfile = of.get_file_path ('thumbs')
                    tdir = os.path.dirname (tfile)
                    if not os.path.exists (tdir):
                        os.makedirs (tdir)
                    im.thumbnail((120, 120), Image.ANTIALIAS)
                    twidth, theight = im.size
                    im.save (tfile, 'PNG')

                    of.datetime = datetime.datetime.utcnow()
                    of.data['width'] = width
                    of.data['height'] = height
                    of.data['thumb_width'] = twidth
                    of.data['thumb_height'] = theight

                    document.data.setdefault ('screenshot', {})
                    document.data['screenshot'][lang] = of.id
                except:
                    of.delete ()
            else:
                utils.log ('Skipping image %s' % outfile_rel)

        document.update (name=name)

        return True

pulse.pulsate.docs.DocumentScanner.register_plugin (EvolutionQuickRefDocumentHandler)
