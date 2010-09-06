# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
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

import datetime
import os

import blinq.config
import blinq.utils

import blip.db
import blip.html
import blip.utils
import blip.web

import blip.plugins.index.web


################################################################################
## Pages

class AllPeopleResponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) == 1 and request.path[0] == 'person':
            return True
        return False

    @classmethod
    def respond (cls, request):
        if len(request.path) != 1 or request.path[0] != 'person':
            return None

        response = blip.web.WebResponse (request)

        page = blip.html.Page (request=request)
        page.set_title (blip.utils.gettext ('People'))
        people = blip.db.Entity.select (type=u'Person')
        people = people.order_by (blip.db.Desc (blip.db.Entity.score))

        page.add_content(blip.html.Div(blip.utils.gettext('42 most active people:')))
        for person in people[:42]:
            lbox = blip.html.LinkBox (person)
            lbox.add_fact (blip.utils.gettext ('score'), str(person.score))
            lbox.add_graph (blinq.config.web_files_url + 'graphs/' +
                            '/'.join(person.ident.split('/')[1:] + ['commits-tight.png']))
            page.add_content (lbox)

        response.payload = page
        return response


class PersonReponder (blip.web.RecordLocator, blip.web.PageResponder):
    @classmethod
    def locate_record (cls, request):
        if len(request.path) != 2 or request.path[0] != 'person':
            return False
        ident = u'/' + request.path[0] + u'/' + request.path[1]
        request.record = blip.db.Entity.get (ident)
        return True

    @classmethod
    def respond (cls, request):
        if len(request.path) != 2 or request.path[0] != 'person':
            return None

        response = blip.web.WebResponse (request)

        if request.record is None:
            page = blip.html.PageNotFound (None)
            response.payload = page
            return response

        page = blip.html.Page (request=request)
        response.payload = page

        # Teams
        rels = blip.db.TeamMember.get_related (pred=request.record)
        rels = blinq.utils.attrsorted (list(rels), ('subj', 'title'))
        if len(rels) > 0:
            box = blip.html.SidebarBox (blip.utils.gettext ('Teams'))
            page.add_sidebar_content (box)
            for rel in rels:
                lbox = box.add_link_box (rel.subj)
                if rel.coordinator:
                    lbox.add_badge ('coordinator')

        # Blog
        bident = u'/blog' + request.record.ident
        blog = blip.db.Forum.select_one (ident=bident)
        if blog is not None:
            box = blip.html.SidebarBox (blip.utils.gettext ('Blog'))
            page.add_sidebar_content (box)
            dl = blip.html.DefinitionList ()
            box.add_content (dl)
            for entry in blog.forum_posts.all()[:6]:
                link = blip.html.Link (entry.web, entry.title)
                dl.add_term (link)
                if entry.datetime != None:
                    dl.add_entry (entry.datetime.strftime('%Y-%m-%d %T'))

        return response


################################################################################
## Tabs

class OverviewTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if len(request.path) != 2 or request.path[0] != 'person':
            return None
        page.add_tab ('overview',
                      blip.utils.gettext ('Overview'),
                      blip.html.TabProvider.FIRST_TAB)
        page.add_to_tab ('overview', cls.get_tab (request))

    @classmethod
    def get_tab (cls, request):
        tab = blip.html.PaddingBox ()

        facts = blip.html.FactsTable ()
        tab.add_content (facts)

        facts.start_fact_group ()
        if request.record.name is not None:
            facts.add_fact (blip.utils.gettext ('Name'), request.record.title)
        if request.record.nick is not None:
            facts.add_fact (blip.utils.gettext ('Nick'), request.record.nick)

        facts.start_fact_group ()
        if request.record.email != None:
            facts.add_fact (blip.utils.gettext ('Email'),
                            blip.html.Link ('mailto:' + request.record.email,
                                            request.record.email))
        if request.record.web != None:
            facts.add_fact (blip.utils.gettext ('Website'),
                            blip.html.Link (request.record.web))

        facts.start_fact_group ()
        span = blip.html.Span (divider=blip.html.SPACE)
        span.add_content (str(request.record.score))
        lt = blip.db.Entity.select (blip.db.Entity.type == u'Person',
                                    blip.db.Entity.score != 0,
                                    blip.db.Entity.score <= request.record.score)
        lt = lt.count()
        gt = blip.db.Entity.select (blip.db.Entity.type == u'Person',
                                    blip.db.Entity.score > request.record.score)
        gt = gt.count()
        span.add_content ('(%.2f%%)' % ((100.0 * lt) / (lt + gt)))
        facts.add_fact (blip.utils.gettext ('Score'), span)

        return tab

    @classmethod
    def respond (cls, request):
        if len(request.path) != 2 or request.path[0] != 'person':
            return None
        if not blip.html.TabProvider.match_tab (request, 'overview'):
            return None

        response = blip.web.WebResponse (request)

        response.payload = cls.get_tab (request)
        return response


################################################################################
## IndexContent

class PeopleIndexContentProvider (blip.plugins.index.web.IndexContentProvider):
    @classmethod
    def provide_content (cls, page, response):
        """Construct an info box for the index page"""
        box = blip.html.SectionBox (blip.utils.gettext ('People'))
        page.add_content (box)

        txt = (blip.utils.gettext ('Blip is watching %i people.') %
               blip.db.Entity.select (type=u'Person').count() )
        box.add_content (blip.html.Div (txt))

        columns = blip.html.ColumnBox (2)
        box.add_content (columns)

        people = blip.db.Entity.select (type=u'Person')

        active = people.order_by (blip.db.Desc (blip.db.Entity.score))
        bl = blip.html.BulletList ()
        bl.set_title (blip.utils.gettext ('Active people:'))
        columns.add_to_column (0, bl)
        for person in active[:6]:
            bl.add_link (person)

        recent = people.order_by (blip.db.Desc (blip.db.Entity.score_diff))
        bl = blip.html.BulletList ()
        bl.set_title (blip.utils.gettext ('Recently active:'))
        columns.add_to_column (1, bl)
        for person in recent[:6]:
            bl.add_link (person)

################################################################################

# FIXME
def get_hacking_tab (person, **kw):
    columns = blip.html.ColumnBox (2)

    # Modules
    rels = blip.db.ModuleEntity.get_related (pred=person)
    rels = blinq.utils.attrsorted (list(rels),
                                   ('subj', 'title'),
                                   ('-', 'subj', 'is_default'),
                                   ('-', 'subj', 'scm_branch'))
    if len(rels) > 0:
        brs = []
        mods = blip.utils.odict()
        bmaint = 0
        for rel in rels:
            mod = rel.subj
            if mod.branchable in brs:
                continue
            brs.append (mod.branchable)
            mods[mod] = rel
        box = blip.html.InfoBox (blip.utils.gettext ('Modules'))
        box.set_id ('modules')
        columns.add_to_column (0, box)
        for mod in mods:
            lbox = box.add_link_box (mod)
            if rel.maintainer:
                lbox.add_badge ('maintainer')
                bmaint += 1
        if 0 < bmaint < len(mods):
            box.add_badge_filter ('maintainer')

    # Documents
    rels = blip.db.DocumentEntity.get_related (pred=person)
    rels = blinq.utils.attrsorted (list(rels),
                                   ('subj', 'title'),
                                   ('-', 'subj', 'is_default'),
                                   ('-', 'subj', 'scm_branch'))
    if len(rels) > 0:
        brs = []
        docs = blip.utils.odict()
        bmaint = bauth = bedit = bpub = 0
        for rel in rels:
            doc = rel.subj
            if doc.branchable in brs:
                continue
            brs.append (doc.branchable)
            docs[doc] = rel
        box = blip.html.InfoBox (blip.utils.gettext ('Documents'))
        box.set_id ('documents')
        columns.add_to_column (1, box)
        for doc in docs:
            lbox = box.add_link_box (doc)
            rel = docs[doc]
            if rel.maintainer:
                lbox.add_badge ('maintainer')
                bmaint += 1
            if rel.author:
                lbox.add_badge ('author')
                bauth += 1
            if rel.editor:
                lbox.add_badge ('editor')
                bedit += 1
            if rel.publisher:
                lbox.add_badge ('publisher')
                bpub += 1
        if 0 < bmaint < len(docs):
            box.add_badge_filter ('maintainer')
        if 0 < bauth < len(docs):
            box.add_badge_filter ('author')
        if 0 < bedit < len(docs):
            box.add_badge_filter ('editor')
        if 0 < bpub < len(docs):
            box.add_badge_filter ('publisher')

    return columns
