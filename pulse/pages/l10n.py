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
import pulse.graphs
import pulse.html
import pulse.models as db
import pulse.parsers
import pulse.scm
import pulse.utils

def main (path, query, http=True, fd=None):
    """Output information about translations"""
    ident = '/' + '/'.join(path)
    if len(path) == 7:
        po = db.Branch.objects.filter (ident=ident)
        try:
            po = po[0]
            branchable = po.branchable
        except IndexError:
            po = branchable = None
    elif len(path) == 6:
        branchable = db.Branchable.objects.filter (ident=ident)
        try:
            branchable = branchable[0]
            po = branchable.get_default ()
        except IndexError:
            po = branchable = None
    else:
        kw = {'http' : http}
        kw['title'] = pulse.utils.gettext ('Invalid Identifier')
        page = pulse.html.PageError (
            pulse.utils.gettext ('The identifier %s is not valid') % ident,
            **kw)
        page.output (fd=fd)
        return 500

    if po == None:
        kw = {'http' : http}
        kw['title'] = pulse.utils.gettext ('Translation Not Found')
        page = pulse.html.PageNotFound (
            pulse.tuils.gettext ('No document with the identifier %s could be found')
            % ident,
            **kw)
        page.output (fd=fd)
        return 404
        
    kw = {'path' : path, 'query' : query, 'http' : http, 'fd' : fd}
    return output_translation (po, branchable, **kw)


def output_translation (po, branchable, **kw):
    """Output information about a translation"""
    lang = po.scm_file[:-3]
    page = pulse.html.Page (po, http=kw.get('http', True))
    checkout = pulse.scm.Checkout.from_record (po, checkout=False, update=False)

    branches = pulse.utils.attrsorted (list(branchable.branches.all()),
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
        of = db.OutputFile.objects.get (type='l10n', ident=po.parent.ident, filename=po.scm_file)
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
            page.add_fact ('foo', 'bar')
            ofs = db.OutputFile.objects.filter (type='figures', ident=parent.ident,
                                                subdir__in=['C', lang])
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
                    commit = db.Revision.get_last_revision (branch=module, files=files)
                    if commit != None:
                        span = pulse.html.Span(divider=pulse.html.SPACE)
                        # FIXME: i18n, word order, but we want to link person
                        mspan = pulse.html.Span()
                        mspan.add_content (commit.datetime.strftime('%Y-%m-%d %T'))
                        mspan.add_class ('mtime')
                        span.add_content (mspan)
                        span.add_content (' by ')
                        person = db.Entity.get_cached (commit.person_id)
                        span.add_content (pulse.html.Link (person))
                        dl.add_entry (span)
                else:
                    dl.add_entry (entry)
                comment = po.data.get('figures', {}).get(figure, {}).get('comment', '')
                if comment == '':
                    comment = parent.data.get('figures', {}).get(figure, {}).get('comment', '')
                if comment != '':
                    dl.add_entry (pulse.html.EllipsizedLabel (comment, 80),
                                  classname='desc')

    page.output(fd=kw.get('fd'))

    return 0
