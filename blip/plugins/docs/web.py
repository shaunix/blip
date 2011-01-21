# coding=UTF-8
# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
#
# This file is part of Blip, a program for displaying various statistics
# of questionable relevance about software and the people who make it.
#
# Blip is free software; you can redistribute it and/or modify it under the
# terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# Blip is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along
# with Blip; if not, write to the Free Software Foundation, 59 Temple Place,
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
        if not ((len(request.path) in (4, 5) and request.path[0] == 'doc') or
                (len(request.path) in (6, 7) and request.path[0] == 'page')):
            return False
        ident = u'/' + u'/'.join(request.path)
        if ((request.path[0] == 'doc' and len(request.path) == 4) or
            (request.path[0] == 'page' and len(request.path) == 6)):
            docs = list(blip.db.Branch.select (project_ident=ident))
            if len(docs) == 0:
                return True
            doc = [doc for doc in docs if doc.is_default]
            if len(doc) == 0:
                return True
            request.record = doc[0]
        else:
            doc = blip.db.Branch.get (ident)
            if doc is None:
                return True
            request.record = doc
            docs = list(blip.db.Branch.select (project_ident=doc.project_ident))
        request.set_data ('branches', docs)
        return True

    @classmethod
    def respond (cls, request, **kw):
        if len(request.path) < 1 or request.path[0] not in ('doc', 'page'):
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page

        if request.record.type == u'DocumentPage':
            page.add_trail_link (request.record.parent.parent.blip_url + '#docs',
                                 request.record.parent.parent.title)
            page.add_trail_link (request.record.parent.blip_url + '#pages',
                                 request.record.parent.title)
        else:
            page.add_trail_link (request.record.parent.blip_url + '#docs',
                                 request.record.parent.title)

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
        if len(request.path) < 1 or request.path[0] not in ('doc', 'page'):
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

        facts.start_fact_group ()
        if request.record.type == u'Document':
            facts.add_fact (blip.utils.gettext ('Document'), request.record.title)
            module = request.record.parent
        else:
            facts.add_fact (blip.utils.gettext ('Page'), request.record.title)
            module = request.record.parent.parent
        if request.record.desc not in (None, ''):
            facts.add_fact (blip.utils.gettext ('Description'),
                            request.record.desc)

        sel = blip.db.Selection (blip.db.SetModule,
                                 blip.db.SetModule.pred_ident == module.ident)
        blip.db.SetModule.select_subj (sel)
        rels = sel.get_sorted (('[subj]', 'title'))
        if len(rels) > 0:
            span = blip.html.Span (*[blip.html.Link(rel['subj']) for rel in rels])
            span.set_divider (blip.html.BULLET)
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Release Sets'), span)

        if request.record.type == u'DocumentPage':
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Document'),
                            blip.html.Link (request.record.parent))
            facts.add_fact (blip.utils.gettext ('Page ID'),
                            request.record.ident.split('/')[2])

        facts.start_fact_group ()
        checkout = blip.scm.Repository.from_record (request.record, checkout=False, update=False)
        facts.add_fact (blip.utils.gettext ('Module'),
                        blip.html.Link (module.blip_url,
                                        request.record.scm_module))
        facts.add_fact (blip.utils.gettext ('Branch'), request.record.scm_branch)
        facts.add_fact (blip.utils.gettext ('Location'), checkout.location)
        if request.record.scm_dir is not None:
            if request.record.scm_file is not None:
                facts.add_fact (blip.utils.gettext ('File'),
                                os.path.join (request.record.scm_dir, request.record.scm_file))
            else:
                facts.add_fact (blip.utils.gettext ('Directory'), request.record.scm_dir)

        facts.start_fact_group ()
        status = request.record.data.get ('docstatus', '00none')
        if status is None:
            status = '00none'
        span = blip.html.Span (status[2:], divider=blip.html.SPACE)
        docdate = request.record.data.get ('docdate', None)
        if docdate is not None:
            span.add_content ('(%s)' % docdate)
        facts.add_fact (blip.utils.gettext ('Status'), span)
        if request.record.subtype is not None:
            facts.add_fact (blip.utils.gettext ('Type'), request.record.subtype)

        if request.record.mod_datetime is not None:
            facts.start_fact_group ()
            if request.record.mod_person_ident is not None:
                facts.add_fact (blip.utils.gettext ('Modified'),
                                blip.html.Link (request.record.mod_person))
                facts.add_fact ('',
                                request.record.mod_datetime.strftime('%Y-%m-%d %T'))
            else:
                facts.add_fact (blip.utils.gettext ('Modified'),
                                request.record.mod_datetime.strftime('%Y-%m-%d %T'))

        if request.record.updated is not None:
            facts.start_fact_group ()
            facts.add_fact (blip.utils.gettext ('Last Updated'),
                            request.record.updated.strftime('%Y-%m-%d %T'))

        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] not in ('doc', 'page'):
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
        return response

class DevelopersTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] not in ('doc', 'page'):
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                (request.record.type == u'Document' or
                 request.record.type == u'DocumentPage')):
            return None
        cnt = blip.db.DocumentEntity.count_related (subj=request.record)
        if cnt > 0:
            page.add_tab ('developers',
                          blip.utils.gettext ('Developers (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] not in ('doc', 'page'):
            return None
        if not blip.html.TabProvider.match_tab (request, 'developers'):
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

class FilesTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                request.record.type == u'Document'):
            return None
        cnt = len (request.record.data.get ('scm_files', []))
        if cnt > 0:
            page.add_tab ('files',
                          blip.utils.gettext ('Files (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not blip.html.TabProvider.match_tab (request, 'files'):
            return None

        response = blip.web.WebResponse (request)

        tab = blip.html.ContainerBox ()

        terms = blip.html.DefinitionList ()
        tab.add_content (terms)
        for filename in request.record.data.get ('scm_files', []):
            terms.add_term (filename)
            rev = blip.db.Revision.get_last_revision (branch=request.record.parent,
                                                      files=[os.path.join (request.record.scm_dir,
                                                                           filename) ])
            if rev is not None:
                terms.add_entry (rev.datetime.strftime ('%Y-%m-%d %T'))

        response.payload = tab
        return response

class PagesTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not (isinstance (request.record, blip.db.Branch) and
                request.record.type == u'Document'):
            return None
        cnt = request.record.select_children (u'DocumentPage').count ()
        if cnt > 0:
            page.add_tab ('pages',
                          blip.utils.gettext ('Pages (%i)') % cnt,
                          blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if len(request.path) < 1 or request.path[0] != 'doc':
            return None
        if not blip.html.TabProvider.match_tab (request, 'pages'):
            return None

        response = blip.web.WebResponse (request)

        tab = blip.html.PaddingBox ()

        meter = blip.html.Meter ()
        tab.add_content (meter)

        cont = blip.html.ContainerBox ()
        tab.add_content (cont)
        cont.add_sort_link ('title', blip.utils.gettext ('title'), 1)
        cont.add_sort_link ('pageid', blip.utils.gettext ('page'))
        cont.add_sort_link ('status', blip.utils.gettext ('status'))

        pages = blinq.utils.attrsorted (list (request.record.select_children (u'DocumentPage')),
                                        'title')
        stats = {}
        for page in pages:
            lbox = cont.add_link_box (page)
            lbox.add_fact (blip.utils.gettext ('page'),
                           blip.html.Span(page.ident.split('/')[2],
                                          html_class='pageid'))
            status = page.data.get ('docstatus', '00none')
            if status is None:
                status = '00none'
            stats.setdefault (status, 0)
            stats[status] = stats[status] + 1
            span = blip.html.Span(status[2:], html_class='status')
            span.add_data_attribute ('sort-key', status[:2])
            lbox.add_fact (blip.utils.gettext ('status'), span)
            docdate = page.data.get ('docdate', None)

        for status in sorted (stats.keys(), reverse=True):
            # Scale up by 10, because numbers are usually low.
            meter.add_bar (10 * stats[status],
                           blip.utils.gettext ('%s (%i)') % (status[2:], stats[status]))

        response.payload = tab
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
            sel = blip.db.Selection (blip.db.Branch,
                                     blip.db.Branch.type == u'Document',
                                     blip.db.Branch.parent_ident == request.record.ident)
        elif request.record.type == u'Set':
            sel = blip.db.Selection (blip.db.Branch,
                                     blip.db.Branch.type == u'Document')
            sel.add_join (blip.db.SetModule,
                          blip.db.SetModule.pred_ident == blip.db.Branch.parent_ident)
            sel.add_where (blip.db.SetModule.subj_ident == request.record.ident)
        else:
            return None

        response = blip.web.WebResponse (request)

        cont = blip.html.ContainerBox ()
        cont.add_sort_link ('title', blip.utils.gettext ('title'), 1)
        if request.record.type == u'Set':
            cont.add_sort_link ('module', blip.utils.gettext ('module'))
        cont.add_sort_link ('status', blip.utils.gettext ('status'))
        cont.add_sort_link ('type', blip.utils.gettext ('type'))

        blip.db.Branch.select_parent (sel)
        stats = {}
        for doc in sel.get_sorted ('title'):
            lbox = cont.add_link_box (doc)
            if request.record.type == u'Set':
                lbox.add_fact (blip.utils.gettext ('module'),
                               blip.html.Span(blip.html.Link (doc['parent'].blip_url,
                                                              doc['parent'].branch_module),
                                              html_class='module'))
            status = doc.data.get ('docstatus', '00none')
            if status is None:
                status = '00none'
            stats.setdefault (status, 0)
            stats[status] = stats[status] + 1
            span = blip.html.Span(status[2:], html_class='status')
            span.add_data_attribute ('sort-key', status[:2])
            lbox.add_fact (blip.utils.gettext ('status'), span)
            if doc.subtype is not None:
                lbox.add_fact (blip.utils.gettext ('type'),
                               blip.html.Span(doc.subtype, html_class='type'))

        if len(stats.keys()) > 1:
            tab = blip.html.PaddingBox ()
            meter = blip.html.Meter ()
            tab.add_content (meter)
            tab.add_content (cont)
            for status in sorted (stats.keys(), reverse=True):
                # Scale up by 10, because numbers are usually low.
                meter.add_bar (10 * stats[status],
                               blip.utils.gettext ('%s (%i)') % (status[2:], stats[status]))
        else:
            tab = cont

        response.payload = tab
        return response
