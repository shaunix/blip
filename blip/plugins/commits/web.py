# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

import blip.db
import blip.html


class CommitsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if request.record is None:
            return
        if not isinstance (request.record, blip.db.Branch):
            return
        page.add_tab ('commits',
                      blip.utils.gettext ('Commits'),
                      blip.html.TabProvider.CORE_TAB)

    @classmethod
    def respond (cls, request):
        if request.record is None:
            return None
        if not isinstance (request.record, blip.db.Branch):
            return None
        if not blip.html.TabProvider.match_tab (request, 'commits'):
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.Div ()
        of = blip.db.OutputFile.select (type=u'graphs',
                                        ident=request.record.ident,
                                        filename=u'commits-0.png')
        try:
            of = of[0] 
            graph = blip.html.Graph.activity_graph (of,
                                                    request.record.blip_url,
                                                    'commits', utils.gettext ('%i commits'),
                                                    'activity', {'action': 'commits'})
            tab.add_content (graph)
        except IndexError:
            pass

        revs = blip.db.Revision.select_revisions (branch=request.record,
                                                  week_range=(blip.utils.weeknum()-52,))
        cnt = revs.count()
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
            span.add_content (rev.display_revision (request.record))
            span.add_content ('on')
            span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
            span.add_content ('by')
            span.add_content (blip.html.Link (rev.person))
            dl.add_term (span)
            dl.add_entry (blip.html.PopupLink.from_revision (rev, 'activity',
                                                             branch=request.record))
        return div

    def handle_request (self):
        contents = None
        action = self.handler.request.query.get ('action')
        if action == 'commits':
            contents = self.get_commits_action ()
        elif action == 'graphmap':
            contents = self.get_graphmap_action ()
        elif action == 'revfiles':
            contents = self.get_revfiles_action ()
        elif action == 'tab':
            contents = self.get_tab ()
        if contents is not None:
            self.handler.response.set_contents (contents)


    def get_commits_action (self):
        weeknum = self.handler.request.query.get('weeknum', None)
        if weeknum != None:
            weeknum = int(weeknum)
            thisweek = utils.weeknum ()
            ago = thisweek - weeknum
            revs = db.Revision.select_revisions (branch=self.handler.record,
                                                 weeknum=weeknum)
            cnt = revs.count()
            revs = list(revs[:20])
        else:
            revs = db.Revision.select_revisions (branch=self.handler.record,
                                                 week_range=(utils.weeknum()-52,))
            cnt = revs.count()
            revs = list(revs[:10])
        if weeknum == None:
            title = (utils.gettext('Showing %i of %i commits:')
                     % (len(revs), cnt))
        elif ago == 0:
            title = (utils.gettext('Showing %i of %i commits from this week:')
                     % (len(revs), cnt))
        elif ago == 1:
            title = (utils.gettext('Showing %i of %i commits from last week:')
                     % (len(revs), cnt))
        else:
            title = (utils.gettext('Showing %i of %i commits from %i weeks ago:')
                     % (len(revs), cnt, ago))
        return self.get_commits_div (revs, title)

    def get_graphmap_action (self):
        id = self.handler.request.query.get ('id')
        num = self.handler.request.query.get ('num')
        filename = self.handler.request.query.get ('filename')

        graph = None
        of = db.OutputFile.select (type=u'graphs', ident=self.handler.record.ident, filename=filename)
        try:
            of = of[0]
            graph = html.Graph.activity_graph (of, self.handler.record.pulse_url,
                                               'commits', utils.gettext ('%i commits'),
                                               'activity', {'action': 'commits'},
                                               count=int(id), num=int(num), map_only=True)
        except:
            pass
        return graph

    def get_revfiles_action (self):
        module = self.handler.record
        if module.scm_server.endswith ('/svn/'):
            base = module.scm_server[:-4] + 'viewvc/'
            colon = base.find (':')
            if colon < 0:
                response.http_status = 404
                return
            if base[:colon] != 'http':
                base = 'http' + base[colon:]
            if module.scm_path != None:
                base += module.scm_path
            elif module.scm_branch == 'trunk':
                base += module.scm_module + '/trunk/'
            else:
                base += module.scm_module + '/branches/' + module.scm_branch + '/'

        revid = self.handler.request.query.get('revid', None)
        revision = db.Revision.get (revid)
        files = db.RevisionFile.select (revision=revision)

        mlink = html.MenuLink (revision.revision, menu_only=True)
        for file in files:
            url = base + file.filename
            url += '?r1=%s&r2=%s' % (file.prevrev, file.filerev)
            mlink.add_link (url, file.filename)

        return mlink
