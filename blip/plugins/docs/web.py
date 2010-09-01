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

import math
import os.path

import blinq.utils

import blip.db
import blip.html
import blip.utils

import blip.plugins.modules.web

class DocumentResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) not in (4, 5) or request.path[0] != 'doc':
            return False
        ident = u'/' + u'/'.join(request.path)
        if len(request.path) == 4:
            docs = list(blip.db.Branch.select (project_ident=ident))
            if len(docs) == 0:
                exception = blip.web.WebException (
                    blip.utils.gettext ('Document Not Found'),
                    blip.utils.gettext ('Blip could not find the document %s in the module %s on %s')
                    % (request.path[3], request.path[2], request.path[1]))
                request.set_data ('exception', exception)
                return True
            doc = [doc for doc in docs if doc.is_default]
            if len(doc) == 0:
                exception = blip.web.WebException (
                    blip.utils.gettext ('Default Branch Not Found'),
                    blip.utils.gettext ('Blip could not find the default branch for the document %s in the module %s on %s')
                    % (request.path[3], request.path[2], request.path[1]))
                request.set_data ('exception', exception)
                return True
            request.record = doc[0]
        else:
            doc = blip.db.Branch.get (ident)
            if doc is None:
                exception = blip.web.WebException (
                    blip.utils.gettext ('Document Not Found'),
                    blip.utils.gettext ('Blip could not find the document %s in the module %s on %s')
                    % (request.path[3], request.path[2], request.path[1]))
                request.set_data ('exception', exception)
                return True
            request.record = doc
            docs = list(blip.db.Branch.select (project_ident=doc.project_ident))
        request.set_data ('branches', docs)
        return True

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) not in (4, 5) or request.path[0] != 'doc':
            return None

        response = blip.web.WebResponse (request)

        exception = request.get_data ('exception')
        if exception is not None:
            page = blip.html.PageNotFound (exception.desc, title=exception.title)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page

        branches = request.get_data ('branches', [])
        if len(branches) > 1:
            for branch in blinq.utils.attrsorted (branches, '-is_default', 'scm_branch'):
                if branch.ident != request.record.ident:
                    page.add_sublink (branch.blip_url, branch.scm_branch)
                else:
                    page.add_sublink (None, branch.scm_branch)

        if request.record.data.has_key ('screenshot'):
            page.add_screenshot (request.record.data['screenshot'])

        return response

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        page.add_tab ('overview',
                      blip.utils.gettext ('Overview'),
                      blip.html.TabProvider.FIRST_TAB),
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox ()

        for err in blip.db.Error.select (ident=request.record.ident):
            tab.add_content (blip.html.AdmonBox (blip.html.AdmonBox.error, err.message))

        facts = blip.html.FactsTable ()
        tab.add_content (facts)

        facts.add_fact (blip.utils.gettext ('Name'), request.record.title)
        facts.add_fact_divider ()

        if request.record.desc != '':
            facts.add_fact (blip.utils.gettext ('Description'),
                            request.record.desc)
            facts.add_fact_divider ()

        rels = blip.db.SetModule.get_related (pred=request.record.parent)
        if len(rels) > 0:
            sets = blinq.utils.attrsorted ([rel.subj for rel in rels], 'title')
            span = blip.html.Span (*[blip.html.Link(rset.blip_url + '#docs',
                                                    rset.title)
                                     for rset in sets])
            span.set_divider (blip.html.BULLET)
            facts.add_fact (blip.utils.gettext ('Release Sets'), span)
            facts.add_fact_divider ()

        facts.add_fact (blip.utils.gettext ('Module'), blip.html.Link (request.record.parent))

        checkout = blip.scm.Repository.from_record (request.record, checkout=False, update=False)
        facts.add_fact (blip.utils.gettext ('Location'), checkout.location)

        if request.record.mod_datetime is not None:
            span = blip.html.Span(divider=blip.html.SPACE)
            # FIXME: i18n, word order, but we want to link person
            span.add_content (request.record.mod_datetime.strftime('%Y-%m-%d %T'))
            page.add_fact (pulse.utils.gettext ('Last Modified'), span)

        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
        return response

class PeopleTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                request.record.type == u'Document'):
            return None
        cnt = blip.db.DocumentEntity.count_related (subj=request.record)
        if cnt > 0:
            page.add_tab ('people',
                          blip.utils.gettext ('People (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not blip.html.TabProvider.match_tab (request, 'people'):
            return None

        response = blip.web.WebResponse (request)

        tab = blip.html.ContainerBox ()

        rels = blip.db.DocumentEntity.select_related (subj=request.record)
        rels = blinq.utils.attrsorted (list(rels), '-maintainer', ('pred', 'title'))
        for rel in rels:
            lbox = tab.add_link_box (rel.pred)
            for badge in ('maintainer', 'author', 'editor', 'publisher'):
                if getattr (rel, badge) == True:
                    lbox.add_badge (badge)

        response.payload = tab
        return response

class TranslationsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                request.record.type == u'Document'):
            return None
        cnt = blip.db.Branch.select (parent=request.record, type=u'Translation').count ()
        if cnt > 0:
            page.add_tab ('i18n',
                          blip.utils.gettext ('Translations (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not blip.html.TabProvider.match_tab (request, 'i18n'):
            return None

        response = blip.web.WebResponse (request)

        pad = blip.html.PaddingBox ()

        of = blip.db.OutputFile.select_one (type=u'l10n', ident=request.record.ident,
                                            filename=(request.record.ident.split('/')[-2] + u'.pot'))
        if of is not None:
            span = blip.html.Span (divider=blip.html.SPACE)
            span.add_content (blip.html.Link (of.blip_url,
                                              blip.utils.gettext ('POT file'),
                                              icon='download'))
            # FIXME: i18n reordering
            span.add_content (blip.utils.gettext ('(%i messages)') % of.statistic)
            span.add_content (blip.utils.gettext ('on %s') % of.datetime.strftime('%Y-%m-%d %T'))
            pad.add_content (span)

        translations = blip.db.Branch.select_with_statistic ([u'Messages', u'ImageMessages'],
                                                             type=u'Translation',
                                                             parent=request.record)
        translations = blinq.utils.attrsorted (list(translations), (0, 'title'))
        if len(translations) == 0:
            pad.add_content (blip.html.AdmonBox (blip.html.AdmonBox.warning,
                                                 blip.utils.gettext ('No translations')))
        else:
            cont = blip.html.ContainerBox ()
            pad.add_content (cont)
            cont.set_sortable_tag ('tr')
            cont.set_sortable_class ('po')
            grid = blip.html.GridBox ()
            cont.add_content (grid)
            sort_percent = False
            sort_images = False
            for translation, mstat, istat in translations:
                span = blip.html.Span (os.path.basename (translation.scm_dir))
                span.add_html_class ('title')
                link = blip.html.Link (translation.blip_url, span)
                row = [link]
                percent = 0
                if mstat is not None:
                    sort_percent = True
                    untranslated = mstat.total - mstat.stat1 - mstat.stat2
                    try:
                        percent = math.floor (100 * (float(mstat.stat1) / mstat.total))
                    except:
                        percent = 0
                    span = blip.html.Span ('%i%%' % percent)
                    span.add_html_class ('percent')
                    row.append (span)
                    row.append (('%i.%i.%i') %
                                (mstat.stat1, mstat.stat2, untranslated))
                if istat is not None:
                    sort_images = True
                    span = blip.html.Span (str(istat.stat1))
                    span.add_html_class ('images')
                    fspan = blip.html.Span (span, '/', str(istat.total), divider = blip.html.SPACE)
                    row.append (fspan)
                idx = grid.add_row (*row)
                grid.add_row_class (idx, 'po')
                if percent >= 0:
                    grid.add_row_class (idx, 'po80')
                elif percent >= 50:
                    grid.add_row_class (idx, 'po50')
            if sort_percent or sort_images:
                cont.add_sort_link ('title', blip.utils.gettext ('language'), 1)
                if sort_percent:
                    cont.add_sort_link ('percent', blip.utils.gettext ('percent'))
                if sort_images:
                    cont.add_sort_link ('images', blip.utils.gettext ('images'))

        response.payload = pad
        return response

class DocumentsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1:
            return None
        if request.record is None:
            return None
        if request.path[0] == 'mod':
            docs = blip.db.Branch.select (type=u'Document',
                                          parent=request.record)
        elif request.path[0] == 'set':
            docs = blip.db.Branch.select (type=u'Document',
                                          parent_in_set=request.record)
        else:
            return None
        cnt = docs.count ()
        if cnt > 0:
            page.add_tab ('docs',
                          blip.utils.gettext ('Documents (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if request.record is None:
            return None
        if not blip.html.TabProvider.match_tab (request, 'docs'):
            return None
        if request.record.type == u'Module':
            docs = blip.db.Branch.select (type=u'Document',
                                          parent=request.record)
        elif request.record.type == u'Set':
            docs = blip.db.Branch.select (type=u'Document',
                                          parent_in_set=request.record)
        else:
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.ContainerBox ()
        tab.set_columns (2)
        if request.record.type == u'Set':
            tab.add_sort_link ('title', blip.utils.gettext ('title'), 1)
            tab.add_sort_link ('module', blip.utils.gettext ('module'))

        for doc in docs.order_by ('name'):
            lbox = tab.add_link_box (doc)
            if request.record.type == u'Set':
                lbox.add_fact (blip.utils.gettext ('module'),
                               blip.html.Span(blip.html.Link (doc.parent.blip_url,
                                                              doc.parent.branch_module),
                                              html_class='module'))
                               

        response.payload = tab
        return response
