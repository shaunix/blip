# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

import blip.db
import blip.html


class CommitsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if request.record is None:
            return
        if not (isinstance (request.record, blip.db.Branch) or
                (isinstance (request.record, blip.db.Entity) and
                 request.record.type == u'Person')):
            return
        page.add_tab ('commits',
                      blip.utils.gettext ('Commits'),
                      blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if request.record is None:
            return None
        if not (isinstance (request.record, blip.db.Branch) or
                (isinstance (request.record, blip.db.Entity) and
                 request.record.type == u'Person')):
            return
        if not blip.html.TabProvider.match_tab (request, 'commits'):
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.Div ()
        of = blip.db.OutputFile.select (type=u'graphs',
                                        ident=request.record.ident,
                                        filename=u'commits-0.png')
        try:
            of = of[0] 
            graph = blip.html.Graph.activity_graph (of, 'commits',
                                                    blip.utils.gettext ('%i commits'))
            tab.add_content (graph)
        except IndexError:
            pass

        if isinstance (request.record, blip.db.Branch):
            cnt = blip.db.RevisionBranch.select (branch=request.record).count ()
        else:
            cnt = blip.db.Revision.select (person=request.record).count ()
        # FIXME: This SELECT is too slow.  Limiting it to 26 weeks to
        # keep the time somewhat sane for now.
        if isinstance (request.record, blip.db.Branch):
            revs = blip.db.Revision.select_revisions (branch=request.record,
                                                      week_range=(blip.utils.weeknum()-26,))
        else:
            revs = blip.db.Revision.select_revisions (person=request.record,
                                                      week_range=(blip.utils.weeknum()-26,))
        revs = list(revs[:10])
        title = (blip.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
        div = cls.get_commits_div (request, revs, title)
        tab.add_content (div)

        response.set_widget (tab)
        return response

    @staticmethod
    def get_commits_div (request, revs, title):
        div = blip.html.Div (widget_id='commits')
        div.add_content (title)
        dl = blip.html.DefinitionList()
        div.add_content (dl)
        curweek = None
        for rev in revs:
            if curweek != None and curweek != rev.weeknum:
                dl.add_divider ()
            curweek = rev.weeknum
            # FIXME: i18n word order
            span = blip.html.Span (divider=blip.html.SPACE)
            if isinstance (request.record, blip.db.Branch):
                span.add_content (rev.display_revision (request.record))
                span.add_content ('on')
                span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
                span.add_content ('by')
                span.add_content (blip.html.Link (rev.person))
                branch = request.record
            else:
                span.add_content (blip.html.Link (rev.project.blip_url, rev.project.title))
                span.add_content ('on')
                span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
                branch = rev.project.default
            dl.add_term (span)
            # FIXME: branch=request.record or...
            dl.add_entry (blip.html.PopupLink.from_revision (rev, 'activity', branch=branch))
        return div


class CommitsGraphMap (blip.web.ContentResponder):
    @classmethod
    def respond (cls, request):
        if request.record is None:
            return None
        if not (isinstance (request.record, blip.db.Branch) or
                (isinstance (request.record, blip.db.Entity) and
                 request.record.type == u'Person')):
            return None
        if request.query.get ('q', None) != 'graphmap':
            return None
        if request.query.get ('graphmap', None) != 'commits':
            return None

        response = blip.web.WebResponse (request)
        graphid = request.query.get ('id')
        num = request.query.get ('num')
        filename = request.query.get ('filename')

        graph = None
        of = blip.db.OutputFile.select (type=u'graphs', ident=request.record.ident, filename=filename)
        try:
            of = of[0]
            graph = blip.html.Graph.activity_graph (of, 'commits',
                                                    blip.utils.gettext ('%i commits'),
                                                    count=int(graphid), num=int(num),
                                                    map_only=True)
            response.set_widget (graph)
            return response
        except:
            pass


class CommitsDiv (blip.web.ContentResponder):
    @classmethod
    def respond (cls, request):
        if request.record is None:
            return None
        if not (isinstance (request.record, blip.db.Branch) or
                (isinstance (request.record, blip.db.Entity) and
                 request.record.type == u'Person')):
            return None
        if request.query.get ('q', None) != 'commits':
            return None

        response = blip.web.WebResponse (request)

        weeknum = request.query.get('weeknum', None)
        if weeknum != None:
            weeknum = int(weeknum)
            thisweek = blip.utils.weeknum ()
            ago = thisweek - weeknum
            if isinstance (request.record, blip.db.Branch):
                revs = blip.db.Revision.select_revisions (branch=request.record,
                                                          weeknum=weeknum)
            else:
                revs = blip.db.Revision.select_revisions (person=request.record,
                                                          weeknum=weeknum)
            cnt = revs.count()
            revs = list(revs[:100])
        else:
            if isinstance (request.record, blip.db.Branch):
                revs = blip.db.Revision.select_revisions (branch=request.record,
                                                          week_range=(utils.weeknum()-52,))
            else:
                revs = blip.db.Revision.select_revisions (person=request.record,
                                                          week_range=(utils.weeknum()-52,))
            cnt = revs.count()
            revs = list(revs[:10])
        if weeknum is None:
            title = (blip.utils.gettext('Showing %i of %i commits:')
                     % (len(revs), cnt))
        elif ago == 0:
            title = (blip.utils.gettext('Showing %i of %i commits from this week:')
                     % (len(revs), cnt))
        elif ago == 1:
            title = (blip.utils.gettext('Showing %i of %i commits from last week:')
                     % (len(revs), cnt))
        else:
            title = (blip.utils.gettext('Showing %i of %i commits from %i weeks ago:')
                     % (len(revs), cnt, ago))

        div = CommitsTab.get_commits_div (request, revs, title)
        response.set_widget (div)
        return response


# def get_revfiles_action (self):
#     module = self.handler.record
#     if module.scm_server.endswith ('/svn/'):
#         base = module.scm_server[:-4] + 'viewvc/'
#         colon = base.find (':')
#         if colon < 0:
#             response.http_status = 404
#             return
#         if base[:colon] != 'http':
#             base = 'http' + base[colon:]
#         if module.scm_path != None:
#             base += module.scm_path
#         elif module.scm_branch == 'trunk':
#             base += module.scm_module + '/trunk/'
#         else:
#             base += module.scm_module + '/branches/' + module.scm_branch + '/'
#     revid = self.handler.request.query.get('revid', None)
#     revision = db.Revision.get (revid)
#     files = db.RevisionFile.select (revision=revision)
#     mlink = html.MenuLink (revision.revision, menu_only=True)
#     for file in files:
#         url = base + file.filename
#         url += '?r1=%s&r2=%s' % (file.prevrev, file.filerev)
#         mlink.add_link (url, file.filename)
#     return mlink
