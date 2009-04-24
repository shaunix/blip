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

from pulse import applications, core, db, html, utils

class ActivityTab (applications.TabProvider):
    application_id = 'activity'
    tab_group = applications.TabProvider.CORE_TAB

    def __init__ (self, handler):
        super (ActivityTab, self).__init__ (handler)

    def get_tab_title (self):
        return utils.gettext ('Activity')

    def handle_request (self):
        contents = None
        action = self.handler.request.query.get ('action')
        if action == 'commits':
            contents = self.get_commits_action ()
        elif action == 'graphmap':
            contents = self.get_graphmap_action ()
        elif action == 'tab':
            contents = self.get_tab ()
        if contents is not None:
            self.handler.response.set_contents (contents)

    def get_tab (self):
        tab = html.Div ()
        of = db.OutputFile.select (type=u'graphs',
                                   ident=self.handler.record.ident,
                                   filename=u'commits-0.png')
        try:
            of = of[0] 
            graph = html.Graph.activity_graph (of,
                                               self.handler.record.pulse_url,
                                               'commits', utils.gettext ('%i commits'),
                                               'activity', {'action': 'commits'})
            tab.add_content (graph)
        except IndexError:
            pass

        revs = db.Revision.select_revisions (branch=self.handler.record,
                                             week_range=(utils.weeknum()-52,))
        cnt = revs.count()
        revs = list(revs[:10])
        title = (utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
        div = self.get_commits_div (revs, title)
        tab.add_content (div)
        return tab

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

    def get_commits_div (self, revs, title):
        div = html.Div (widget_id='commits')
        div.add_content (title)
        dl = html.DefinitionList()
        div.add_content (dl)
        curweek = None
        for rev in revs:
            if curweek != None and curweek != rev.weeknum:
                dl.add_divider ()
            curweek = rev.weeknum
            # FIXME: i18n word order
            span = html.Span (divider=html.SPACE)
            span.add_content (rev.display_revision (self.handler.record))
            span.add_content ('on')
            span.add_content (rev.datetime.strftime('%Y-%m-%d %T'))
            span.add_content ('by')
            span.add_content (html.Link (rev.person))
            dl.add_term (span)
            dl.add_entry (html.PopupLink.from_revision (rev, branch=self.handler.record))
        return div

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

def initialize (handler):
    if handler.__class__.__name__ == 'ModuleHandler':
        handler.register_application (ActivityTab)
