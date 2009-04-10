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

"""Output information about transltions"""

import datetime
import math
import os

import pulse.config
import pulse.db
import pulse.graphs
import pulse.html
import pulse.parsers
import pulse.scm
import pulse.utils

def main (response, path, query):
    """Output information about translations"""
    ident = u'/' + '/'.join(path)
    if len(path) == 7:
        po = pulse.db.Branch.get (ident)
    elif len(path) == 6:
        branches = pulse.db.Branch.select (branchable=ident)
        po = [branch for branch in branches if branch.is_default]
        if len(po) > 0:
            po = po[0]
        else:
            po = None
    else:
        page = pulse.html.PageError (
            pulse.utils.gettext ('The identifier %s is not valid') % ident,
            title=pulse.utils.gettext ('Invalid Identifier'))
        response.set_contents (page)
        return

    if po == None:
        page = pulse.html.PageNotFound (
            pulse.utils.gettext ('No translation with the identifier %s could be found')
            % ident,
            title=pulse.utils.gettext ('Translation Not Found'))
        response.set_contents (page)
        return
        
    kw = {'path' : path, 'query' : query}
    output_translation (response, po, **kw)


def output_translation (response, po, **kw):
    """Output information about a translation"""
    lang = po.scm_file[:-3]
    page = pulse.html.Page (po)
    response.set_contents (page)
    checkout = pulse.scm.Checkout.from_record (po, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(pulse.db.Branch.select (branchable=po.branchable)),
                                       '-is_default', 'scm_branch')
    if len(branches) > 1:
        for branch in branches:
            if branch.ident != po.ident:
                page.add_sublink (branch.pulse_url, branch.ident.split('/')[-1])
            else:
                page.add_sublink (None, branch.ident.split('/')[-1])

    # Facts
    parent = po.parent
    module = parent.parent
    page.add_fact (pulse.utils.gettext ('Module'), module)
    if parent.type == 'Document':
        page.add_fact (pulse.utils.gettext ('Document'), parent)
    else:
        page.add_fact (pulse.utils.gettext ('Domain'), parent)

    page.add_fact_divider ()
    page.add_fact (pulse.utils.gettext ('Location'),
                   checkout.get_location (po.scm_dir, po.scm_file))
    if po.mod_datetime != None:
        span = pulse.html.Span(divider=pulse.html.SPACE)
        # FIXME: i18n, word order, but we want to link person
        span.add_content (po.mod_datetime.strftime('%Y-%m-%d %T'))
        if po.mod_person != None:
            span.add_content (' by ')
            span.add_content (pulse.html.Link (po.mod_person))
        page.add_fact (pulse.utils.gettext ('Last Modified'), span)

    try:
        of = pulse.db.OutputFile.select (type=u'l10n', ident=po.parent.ident, filename=po.scm_file)
        of = of[0]
        pofile = pulse.parsers.Po (of.get_file_path ())
        form = pulse.html.TranslationForm()
        page.add_content (form)
        for msgkey in pofile.get_messages():
            entry = form.add_entry (msgkey)
            entry.set_comment (pofile.get_comment (msgkey))
            if pofile.has_message (msgkey):
                entry.set_translated (pofile.get_translations (msgkey))
    except:
        pass

    # Figures
    if parent.type == 'Document':
        figures = sorted (parent.data.get('figures', []))
        if len(figures) > 0:
            ofs = pulse.db.OutputFile.select (pulse.db.OutputFile.type == u'figures',
                                              pulse.db.OutputFile.ident == parent.ident,
                                              pulse.db.OutputFile.subdir.is_in ((u'C', lang)))
            ofs_by_source_C = {}
            ofs_by_source_lc = {}
            for of in ofs:
                if of.subdir == 'C':
                    ofs_by_source_C[of.source] = of
                else:
                    ofs_by_source_lc[of.source] = of
            box = pulse.html.InfoBox (pulse.utils.gettext ('Figures'))
            page.add_content (box)
            dl = pulse.html.DefinitionList ()
            box.add_content (dl)
            for figure in figures:
                of = ofs_by_source_C.get(figure)
                if of:
                    dl.add_term (pulse.html.Link (of.pulse_url, figure, classname='zoom'))
                else:
                    dl.add_term (figure)

                status = po.data.get('figures', {}).get(figure, {}).get('status')
                if status == 'translated':
                    entry = pulse.utils.gettext ('translated')
                elif status == 'fuzzy':
                    entry = pulse.utils.gettext ('fuzzy')
                else:
                    entry = pulse.utils.gettext ('untranslated')
                of = ofs_by_source_lc.get(figure)
                if of:
                    dl.add_entry (pulse.html.Link (of.pulse_url, entry, classname='zoom'))
                    files = [os.path.join (po.scm_dir, of.source)]
                    commit = pulse.db.Revision.get_last_revision (branch=module, files=files)
                    if commit != None:
                        span = pulse.html.Span(divider=pulse.html.SPACE)
                        # FIXME: i18n, word order, but we want to link person
                        mspan = pulse.html.Span()
                        mspan.add_content (commit.datetime.strftime('%Y-%m-%d %T'))
                        mspan.add_class ('mtime')
                        span.add_content (mspan)
                        span.add_content (' by ')
                        span.add_content (pulse.html.Link (commit.person))
                        dl.add_entry (span)
                else:
                    dl.add_entry (entry)
                comment = po.data.get('figures', {}).get(figure, {}).get('comment', '')
                if comment == '':
                    comment = parent.data.get('figures', {}).get(figure, {}).get('comment', '')
                if comment != '':
                    dl.add_entry (pulse.html.EllipsizedLabel (comment, 80),
                                  classname='desc')
