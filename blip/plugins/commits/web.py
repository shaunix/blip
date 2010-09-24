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

import re

import blip.db
import blip.html

import blip.plugins.home.web

def from_revision (rev, app, **kw):
    branch = kw.pop ('branch', None)
    comment = rev.comment
    if comment.strip() == '':
        lnk = cls (blip.html.AdmonBox (blip.html.AdmonBox.warning, blip.utils.gettext ('No comment')),
                   '', **kw)
    else:
        datere = re.compile ('^\d\d\d\d-\d\d-\d\d ')
        colonre = re.compile ('^\* [^:]*:(.*)')
        maybe = ''
        for line in comment.split('\n'):
            line = line.strip()
            if line == '':
                pass
            elif datere.match(line):
                maybe = line
            else:
                cmatch = colonre.match(line)
                if cmatch:
                    line = cmatch.group(1).strip()
                    if line != '':
                        break
                else:
                    break
        if line == '':
            line = maybe
        if len(line) > 80:
            i = 60
            while i < len(line):
                if line[i] == ' ':
                    break
                i += 1
            if i < len(comment):
                line = line[:i] + '...'
        lnk = blip.html.PopupLink (line, blip.html.Pre(comment), **kw)
    if branch is None:
        branch = rev.branch
    # if branch.scm_type == 'svn':
    #     if branch.scm_server.endswith ('/svn/'):
    #         base = branch.scm_server[:-4] + 'viewvc/'
    #         colon = base.find (':')
    #         if colon < 0:
    #             return lnk
    #         if base[:colon] != 'http':
    #             base = 'http' + base[colon:]
    #         if branch.scm_path != None:
    #             base += branch.scm_path
    #         elif branch.scm_branch == 'trunk':
    #             base += branch.scm_module + '/trunk'
    #         else:
    #             base += branch.scm_module + '/branches/' + branch.scm_branch
    #         mlink = blip.html.MenuLink (rev.revision, 'files')
    #         mlink.set_menu_url ('%s?application=%s&action=revfiles&revid=%s'
    #                             % (branch.blip_url, app, str(rev.ident)))
    #         lnk.add_link (mlink)
    #         infourl = base + '?view=revision&revision=' + rev.revision
    #         lnk.add_link (infourl, blip.utils.gettext ('info'))
    return lnk

class CommitMessageFormatter (blip.plugins.home.web.MessageFormatter):
    @classmethod
    def format_message (cls, message, record):
        if message.type == u'commit':
            box = blip.html.ActivityBox (subject=record,
                                         datetime=message.datetime.strftime('%Y-%m-%d'))
            if isinstance (record, blip.db.Entity):
                span = blip.html.Span (' made %i commits to ' % message.count)
                proj = blip.db.Project.get (message.pred)
                span.add_content (blip.html.Link (proj.default))
                box.set_message (span)
            else:
                box.set_message (' had %i commits' % message.count)
            return box
        return None

class CommitsTab (blip.html.TabProvider):
    @classmethod
    def add_tabs (cls, page, request):
        if request.record is None:
            return
        if not ((isinstance (request.record, blip.db.Branch) and
                 request.record.type == u'Module') or
                (isinstance (request.record, blip.db.Entity) and
                 request.record.type == u'Person') ):
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
            return None
        if not blip.html.TabProvider.match_tab (request, 'commits'):
            return None

        response = blip.web.WebResponse (request)
        tab = blip.html.Div ()
        of = blip.db.OutputFile.select_one (type=u'graphs',
                                            ident=request.record.ident,
                                            filename=u'commits-0.png')
        if of is not None:
            graph = blip.html.Graph.activity_graph (of, 'commits',
                                                    blip.utils.gettext ('%i commits'))
            tab.add_content (graph)

        if isinstance (request.record, blip.db.Branch):
            sel = blip.db.Selection (blip.db.Revision)
            blip.db.Revision.select_on_branch (sel, request.record)
            cnt = blip.db.Selection (blip.db.RevisionBranch,
                                     blip.db.RevisionBranch.branch_ident == request.record.ident)
            cnt = cnt.count ()
            blip.db.Revision.select_person (sel)
        else:
            sel = blip.db.Selection (blip.db.Revision,
                                     blip.db.Revision.person_ident == request.record.ident)
            cnt = sel.count ()
            blip.db.Revision.select_branch (sel)
        # This gets slow as the number of revisions increases. We can
        # speed it up by restricting how long ago we search, but that
        # can lead to empty results for less active modules. So the
        # more total commits we have, the harder we clamp.
        ago = blip.utils.weeknum() - int(30000.0/cnt)
        if ago > 0:
            blip.db.Revision.select_on_week_range (sel, (ago,))
        sel.order_by (blip.db.Desc (blip.db.Revision.datetime))
        revs = list(sel[:10])
        title = (blip.utils.gettext('Showing %i of %i commits:') % (len(revs), cnt))
        div = cls.get_commits_div (request, revs, title)
        tab.add_content (div)

        response.payload = tab
        return response

    @staticmethod
    def get_commits_div (request, revs, title):
        div = blip.html.ActivityContainer (html_id='commits')
        div.set_title (title)
        for rev in revs:
            if isinstance (request.record, blip.db.Branch):
                branch = request.record
                act = blip.html.ActivityBox (subject=rev['person'],
                                             datetime=rev.datetime.strftime('%T'))
            else:
                branch = rev['branch']
                act = blip.html.ActivityBox (subject=rev.project,
                                             datetime=rev.datetime.strftime('%T'))
            act.add_info (blip.utils.gettext('revision %s') % rev.display_revision (branch))
            div.add_activity (rev.datetime.strftime('%Y-%m-%d'), act)
            act.add_content (from_revision (rev, 'activity', branch=branch))
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
            response.payload = graph
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
        weeknum = int(weeknum)
        thisweek = blip.utils.weeknum ()
        ago = thisweek - weeknum
        if isinstance (request.record, blip.db.Branch):
            sel = blip.db.Selection (blip.db.Revision,
                                     blip.db.Revision.weeknum == weeknum)
            blip.db.Revision.select_on_branch (sel, request.record)
            cnt = blip.db.Selection (blip.db.RevisionBranch,
                                     blip.db.RevisionBranch.branch_ident == request.record.ident)
            cnt.add_join (blip.db.Revision,
                          blip.db.Revision.ident == blip.db.RevisionBranch.revision_ident)
            cnt.add_where (blip.db.Revision.weeknum == weeknum)
            cnt = cnt.count ()
            blip.db.Revision.select_person (sel)
        else:
            sel = blip.db.Selection (blip.db.Revision,
                                     blip.db.Revision.weeknum == weeknum,
                                     blip.db.Revision.person_ident == request.record.ident)
            cnt = sel.count ()
            blip.db.Revision.select_branch (sel)
        sel.order_by (blip.db.Desc (blip.db.Revision.datetime))
        revs = list(sel[:200])

        if ago == 0:
            if len(revs) == cnt:
                title = (blip.utils.gettext('Showing all %i commits from this week:')
                         % cnt)
            else:
                title = (blip.utils.gettext('Showing %i of %i commits from this week:')
                         % (len(revs), cnt))
        elif ago == 1:
            if len(revs) == cnt:
                title = (blip.utils.gettext('Showing all %i commits from last week:')
                         % cnt)
            else:
                title = (blip.utils.gettext('Showing %i of %i commits from last week:')
                         % (len(revs), cnt))
        else:
            if len(revs) == cnt:
                title = (blip.utils.gettext('Showing all %i commits from %i weeks ago:')
                         % (cnt, ago))
            else:
                title = (blip.utils.gettext('Showing %i of %i commits from %i weeks ago:')
                         % (len(revs), cnt, ago))

        div = CommitsTab.get_commits_div (request, revs, title)
        response.payload = div
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
