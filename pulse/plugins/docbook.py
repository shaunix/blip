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
Common utilities for DocBook-based document plugins
"""

import datetime
import Image
import libxml2
import os
import re
import shutil
import StringIO
import time
import urllib

from pulse import config, db, parsers, utils

class DocBookHandler (object):
    """
    Common utilities for DocBook-based document plugins
    """

    def __init__ (self, handler):
        self.handler = handler
        self.credits = []
        self.figures_by_lang = {}
        self.ofs_by_lang = {}


    def process_docfile (self, docfile, **kw):
        """
        Process a DocBook document for various bits of information.
        """
        document = self.handler.scanner.document
        rel_scm = utils.relative_path (docfile, config.scm_dir)
        if not os.path.exists (docfile):
            utils.warn ('No such file %s' % rel_scm)
            return
        mtime = os.stat(docfile).st_mtime
        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                return
        utils.log ('Processing file %s' % rel_scm)

        title = None
        abstract = None
        try:
            ctxt = libxml2.newParserCtxt()
            xmldoc = ctxt.ctxtReadFile (docfile, None, 0)
            xmldoc.xincludeProcess()
            root = xmldoc.getRootElement()
        except Exception, e:
            utils.warn ('Failed to load file %s' % rel_scm)
            document.error = unicode(e)
            return
        document.error = None
        seen = 0
        releaselinks = []
        document.data['status'] = 'none'
        for node in utils.xmliter (root):
            if node.type != 'element':
                continue
            if node.name[-4:] == 'info':
                seen += 1
                infonodes = list (utils.xmliter (node))
                i = 0
                while i < len(infonodes):
                    infonode = infonodes[i]
                    if infonode.type != 'element':
                        i += 1
                        continue
                    if infonode.name == 'title':
                        if title == None:
                            title = infonode.getContent()
                    elif infonode.name == 'abstract' and infonode.prop('role') == 'description':
                        abstract = infonode.getContent()
                    elif infonode.name == 'releaseinfo':
                        if infonode.prop ('revision') == document.parent.data.get ('series'):
                            document.data['status'] = infonode.prop ('role')
                            for ch in utils.xmliter (infonode):
                                if ch.type == 'element' and ch.name == 'ulink':
                                    releaselinks.append ((ch.prop ('type'), ch.prop ('url'), None))
                    elif infonode.name == 'authorgroup':
                        infonodes.extend (list (utils.xmliter (infonode)))
                    elif infonode.name in ('author', 'editor', 'othercredit'):
                        cr_name, cr_email = personname (infonode)
                        maint = (infonode.prop('role') == 'maintainer')
                        self.credits.append ((cr_name, cr_email, infonode.name, maint))
                    elif infonode.name == 'collab':
                        cr_name = None
                        for ch in utils.xmliter (infonode):
                            if ch.type == 'element' and ch.name == 'collabname':
                                cr_name = normalize (ch.getContent())
                        if cr_name != None:
                            maint = (infonode.prop('role') == 'maintainer')
                            self.credits.append ((cr_name, None, 'collab', maint))
                    elif infonode.name in ('corpauthor', 'corpcredit'):
                        maint = (infonode.prop('role') == 'maintainer')
                        self.credits.append ((normalize (infonode.getContent()),
                                            None, infonode.name, maint))
                    elif infonode.name == 'publisher':
                        cr_name = None
                        for ch in utils.xmliter (infonode):
                            if ch.type == 'element' and ch.name == 'publishername':
                                cr_name = normalize (ch.getContent())
                        if cr_name != None:
                            maint = (infonode.prop('role') == 'maintainer')
                            self.credits.append ((cr_name, None, 'publisher', maint))
                    i += 1
            elif node.name == 'title':
                seen += 1
                title = node.getContent()
            if seen > 1:
                break

        if title != None:
            document.update (name=normalize(title))
        if abstract != None:
            document.update (desc=normalize(abstract))

        oldlinks = {}
        for link in document.data.get ('releaselinks', []):
            oldlinks[link[1]] = link[2]
        for i in range (len (releaselinks)):
            title = oldlinks.get (releaselinks[i][1], None)
            if title == None:
                title = utils.get_html_title (releaselinks[i][1])
            releaselinks[i] = (releaselinks[i][0], releaselinks[i][1], title)
        document.data['releaselinks'] = releaselinks

        # FIXME
        imgs = xmldoc.xpathEval ('//imagedata')
        document.data['figures'] = {}
        document.data['screens'] = {}
        for img in imgs:
            fileref = img.prop ('fileref')
            if fileref == None:
                continue

            par = img.parent
            media = None
            is_screenshot = False
            while par.type == 'element':
                if par.name in ['mediaobject', 'inlinemediaobject']:
                    media = par
                if par.name == 'screenshot':
                    is_screenshot = True
                if is_screenshot:
                    parid = par.prop ('id')
                    if parid != None:
                        document.data['screens'].setdefault (parid, fileref)
                par = par.parent

            comment = ''
            if media != None:
                for text in utils.xmliter (media):
                    if text.type == 'element' and text.name == 'textobject':
                        for phrase in utils.xmliter (text):
                            if phrase.type == 'element' and phrase.name == 'phrase':
                                comment = phrase.getContent()

            if is_screenshot:
                document.data['screens'].setdefault (None, fileref)

            document.data['figures'][fileref] = {'comment': comment}

        db.Timestamp.set_timestamp (rel_scm, mtime)


    def process_translations (self, **kw):
        """
        Process the translations of a DocBook file.
        """
        document = self.handler.scanner.document
        checkout = self.handler.scanner.checkout
        # Coercing into a list, because otherwise this result set stays open,
        # which causes locking issues with subsequent UPDATE commands under
        # SQLite.  Probably not a problem with other databases.  Upper bound
        # on this result set is the number of languages GNOME is translated
        # into.  Be mindful when doing this for larger result sets.
        translations = list(db.Branch.select (type=u'Translation', parent=document))
        for translation in translations:
            pofile = os.path.join (checkout.directory, translation.scm_dir, translation.scm_file)
            self.process_pofile (pofile, **kw)


    def process_pofile (self, pofile, **kw):
        """
        Process a PO file for a DocBook file.
        """
        document = self.handler.scanner.document
        lang = os.path.basename(pofile)[:-3]
        self.figures_by_lang[lang] = []
        for ref in document.data.get ('figures', {}).keys():
            dref = os.path.join (os.path.dirname (pofile), ref)
            if os.path.exists (dref):
                self.figures_by_lang[lang].append (ref)
   
        rel_scm = utils.relative_path (pofile, config.scm_dir)
        if not os.path.exists (pofile):
            utils.warn ('No such file %s' % rel_scm)
            return
        mtime = os.stat(pofile).st_mtime
        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                return
        utils.log ('Processing file %s' % rel_scm)

        po = parsers.Po (pofile)
        if document.name.has_key('C') and po.has_message (document.name['C']):
            document.update (name={lang : po.get_translations (document.name['C'])[0]})
        if document.desc.has_key('C') and po.has_message (document.desc['C']):
            document.update (desc={lang : po.get_translations (document.desc['C'])[0]})

        db.Timestamp.set_timestamp (rel_scm, mtime)


    def process_credits (self, **kw):
        """
        Process the credits found in a DocBook file.
        """
        document = self.handler.scanner.document
        rels = []
        for cr_name, cr_email, cr_type, cr_maint in self.credits:
            ent = None
            if cr_email != None:
                ent = db.Entity.get_or_create_email (cr_email)
            if ent == None:
                ident = u'/ghost/' + urllib.quote (cr_name)
                ent = db.Entity.get_or_create (ident, u'Ghost')
                if ent.ident == ident:
                    ent.update (name=cr_name)
            if cr_name is not None:
                ent.extend (name=cr_name)
            if cr_email is not None:
                ent.extend (email=cr_email)
            rel = db.DocumentEntity.set_related (document, ent)
            if cr_type in ('author', 'corpauthor'):
                rel.author = True
            elif cr_type == 'editor':
                rel.editor = True
            elif cr_type == 'publisher':
                rel.publisher = True
            if cr_maint:
                rel.maintainer = True
            rels.append (rel)
        document.set_relations (db.DocumentEntity, rels)


    def process_figures (self, **kw):
        """
        Process the figures found for a DocBook file.
        """
        document = self.handler.scanner.document
        figures = document.data.get ('figures', {}).keys()
        self.figures_by_lang['C'] = figures
        ofs = list(db.OutputFile.select (type=u'figures', ident=document.ident))
        for of in ofs:
            self.ofs_by_lang.setdefault (of.subdir, [])
            self.ofs_by_lang[of.subdir].append (of)
        for lang in self.figures_by_lang.keys():
            self.ofs_by_lang.setdefault (lang, [])

        for lang in self.ofs_by_lang.keys():
            self.process_figures_for_lang (lang, **kw)


    def process_figures_for_lang (self, lang, **kw):
        """
        Process the figures for a particular language.
        """
        document = self.handler.scanner.document
        checkout = self.handler.scanner.checkout
        figures = self.figures_by_lang.get (lang, [])
        ofs = self.ofs_by_lang[lang]

        indir = os.path.join (checkout.directory, document.scm_dir, document.scm_file)
        indir = os.path.dirname (os.path.dirname (indir))
        indir = os.path.join (indir, lang)
        ofs_by_source = {}
        for of in ofs:
            ofs_by_source[of.source] = of
        screen = document.data.get('screens', {}).get(None, None)
        missing = []
        for ref in figures:
            of = ofs_by_source.pop (ref, None)
            if of == None:
                infile = os.path.join (indir, ref)
                of = db.OutputFile (type=u'figures', ident=document.ident, subdir=lang,
                                    filename=os.path.basename (ref), source=ref,
                                    datetime=datetime.datetime.utcnow())
                copy_image (infile, of)
            else:
                infile = os.path.join (indir, of.source)
                if not kw.get('no_timestamps', False):
                    try:
                        mtime = os.stat(infile).st_mtime
                        if mtime > time.mktime(of.datetime.timetuple()):
                            copy_image (infile, of)
                    except:
                        missing.append (ref)
                else:
                    copy_image (infile, of)
            if ref == screen:
                document.data.setdefault ('screenshot', {})
                document.data['screenshot'][lang] = of.id
        if len(missing) > 0:
            document.error = u'Missing figures: ' + u', '.join (missing)
        for of in ofs_by_source.values():
            utils.log ('Deleting figure %s/%s' % (of.subdir, of.filename))
            try:
                os.remove (of.get_file_path())
                os.remove (of.get_file_path('thumbs'))
            except:
                pass
            of.delete()


def normalize (string):
    """
    Normalize a string from an XML document.
    """
    if string == None:
        return string
    return re.sub('\s+', ' ', string).strip()


def personname (node):
    """
    Get the name of a person from a DocBook node.
    """
    name = [None, None, None, None, None]
    namestr = None
    email = None
    for child in utils.xmliter (node):
        if child.type != 'element':
            continue
        if child.name == 'personname':
            namestr = personname(child)[0]
        elif child.name == 'email':
            email = child.getContent()
        elif namestr == None:
            try:
                i = ['honorific', 'firstname', 'othername', 'surname', 'lineage'].index(child.name)
                if name[i] == None:
                    name[i] = child.getContent()
            except ValueError:
                pass
    if namestr == None:
        while None in name:
            name.remove(None)
        namestr = ' '.join (name)
    return (normalize (namestr), normalize (email))

def copy_image (infile, of):
    if not os.path.exists (infile):
        utils.warn ('Failed to copy figure %s' % of.filename)
        return
    utils.log ('Copying figure %s/%s' % (of.subdir, of.filename))
    outfile = of.get_file_path ()
    outdir = os.path.dirname (outfile)
    if not os.path.exists (outdir):
        os.makedirs (outdir)
    tfile = of.get_file_path ('thumbs')
    tdir = os.path.dirname (tfile)
    if not os.path.exists (tdir):
        os.makedirs (tdir)
    shutil.copyfile (infile, outfile)
    try:
        im = Image.open (infile)
        width, height = im.size
        im.thumbnail((120, 120), Image.ANTIALIAS)
        twidth, theight = im.size
        im.save (tfile, 'PNG')
    except IOError:
        # PIL doesn't do interlaced PNGs.  Process the image with
        # ImageMagick and pipe the result back.
        fd = os.popen ('convert "%s" -interlace none -' % infile)
        # We have to wrap with StringIO because Image.open expects the
        # file object to implement seek, which os.popen does not.
        im = Image.open(StringIO.StringIO(fd.read()))
        im.thumbnail((120, 120), Image.ANTIALIAS)
        twidth, theight = im.size
        im.save (tfile, 'PNG')
    of.datetime = datetime.datetime.utcnow()
    of.data['width'] = width
    of.data['height'] = height
    of.data['thumb_width'] = twidth
    of.data['thumb_height'] = theight
