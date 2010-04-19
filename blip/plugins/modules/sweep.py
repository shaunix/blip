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

"""
Update information from projects and branches
"""

import datetime
import os

import blinq.ext

import blip.db
import blip.graphs
import blip.scm
import blip.sweep
import blip.utils

class ModulesResponder (blip.sweep.SweepResponder):
    command = 'modules'
    synopsis = 'update information about projects and module branches'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] modules [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--no-history',
                                 dest='read_history',
                                 action='store_false',
                                 default=True,
                                 help='do not check SCM history')
        request.add_tool_option ('--no-timestamps',
                                 dest='timestamps',
                                 action='store_false',
                                 default=True,
                                 help='do not check timestamps before processing files')
        request.add_tool_option ('--no-update',
                                 dest='update_scm',
                                 action='store_false',
                                 default=True,
                                 help='do not update SCM repositories')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)
        argv = request.get_tool_args ()
        branches = []
        if len(argv) == 0:
            branches = blip.db.Branch.select (blip.db.Branch.type == u'Module')
        else:
            for arg in argv:
                ident = blip.utils.utf8dec (arg)
                if ident.startswith(u'/set/'):
                    branches += list(blip.db.Branch.select (blip.db.Branch.type == u'Module',
                                                            blip.db.Branch.ident == blip.db.SetModule.pred_ident,
                                                            blip.db.SetModule.subj_ident.like (ident)))
                else:
                    branches += list(blip.db.Branch.select (blip.db.Branch.type == u'Module',
                                                            blip.db.Branch.ident.like (ident)))
        for branch in branches:
            try:
                scanner = ModuleScanner (request, branch)
                scanner.update ()
                blip.db.flush ()
            except:
                blip.db.rollback ()
                raise
            else:
                blip.db.commit ()
        return response


class ModuleFileScanner (blinq.ext.ExtensionPoint):
    def __init__ (self, scanner):
        self.scanner = scanner

    def process_file (self, dirname, basename):
        pass

    def post_process (self):
        pass


class ModuleScanner (object):
    def __init__ (self, request, branch):
        self.request = request
        self.branch = branch
        self._file_scanners = []
        self.repository = blip.scm.Repository.from_record (branch,
                                                           update=request.get_tool_option ('update_scm'))
        for cls in ModuleFileScanner.get_extensions ():
            try:
                scanner = cls (self)
                self._file_scanners.append (scanner)
            except:
                blip.utils.warn ('Could create instance of ' + cls.__name__)
        self._parsed_files = {}
        self._children = {}

    def add_child (self, child):
        self._children.setdefault (child.type, [])
        if child not in self._children[child.type]:
            self._children[child.type].append (child)

    def get_parsed_file (self, parser, filename):
        if not self._parsed_files.has_key ((parser, filename)):
            self._parsed_files[(parser, filename)] = parser (filename)
        return self._parsed_files[(parser, filename)]

    def update (self):
        #    self.branch.update (error=None)
        if self.repository.error is None:
            blip.db.Error.clear_error (self.branch)
        else:
            blip.db.Error.set_error (self.branch, self.repository.error)

        if self.request.get_tool_option ('read_history', True):
            self.check_history ()

        self.update_commit_graphs ()

        def visit (arg, dirname, names):
            ignore = self.repository.ignoredir
            if ignore in names:
                names.remove (ignore)
            for basename in names:
                filename = os.path.join (dirname, basename)
                if not os.path.isfile (filename):
                    continue
                for scanner in self._file_scanners:
                    scanner.process_file (dirname, basename)
        os.path.walk (self.repository.directory, visit, None)

        for scanner in self._file_scanners:
            scanner.post_process ()

        for objtype in self._children.keys ():
            self.branch.set_children (objtype, self._children[objtype])

        self.set_default_child ()

        self.branch.updated = datetime.datetime.utcnow ()
        blip.db.Queue.remove (self.branch.ident)

    def check_history (self):
        since = blip.db.Revision.get_last_revision (branch=self.branch)
        if since is not None:
            since = since.revision
            try:
                # If get_revision isn't implemented (CVS), we can't fast-path skip
                current = self.repository.get_revision()
                if current is not None and since == current[0]:
                    blip.utils.log ('Skipping history for %s' % self.branch.ident)
                    return
            except:
                pass
        blip.utils.log ('Checking history for %s' % self.branch.ident)
        for commit in self.repository.read_history (since=since):
            if commit.author_id is not None:
                person = blip.db.Entity.get_or_create (commit.author_ident, u'Person')
            elif commit.author_email is not None:
                person = blip.db.Entity.get_or_create_email (commit.author_email)
            else:
                person = blip.db.Entity.get_or_create (commit.author_ident, u'Ghost')

            if person.type == u'Person':
                blip.db.Queue.push (person.ident)
            if commit.author_name is not None:
                person.extend (name=commit.author_name)
            if commit.author_email is not None:
                person.extend (email=commit.author_email)
            # IMPORTANT: If we were to just set branch and person, instead of
            # branch_ident and person_ident, Storm would keep referencess to
            # the Revision object.  That would eat your computer.
            revident = self.branch.project.ident + u'/' + commit.id
            if blip.db.Revision.select(ident=revident).count() > 0:
                continue
            rev = {'ident': revident,
                   'project_ident': self.branch.project.ident,
                   'person_ident': person.ident,
                   'revision': commit.id,
                   'datetime': commit.datetime,
                   'comment': commit.comment }
            if person.ident != commit.author_ident:
                rev['alias_ident'] = commit.author_ident
            rev = blip.db.Revision (**rev)
            rev.decache ()
            for filename, filerev, prevrev in commit.files:
                revfile = rev.add_file (filename, filerev, prevrev)
                revfile.decache ()
            rev.add_branch (self.branch)
            blip.db.flush()

        blip.db.Revision.flush_file_cache ()
        revision = blip.db.Revision.get_last_revision (branch=self.branch)
        if revision != None:
            self.branch.mod_datetime = revision.datetime
            self.branch.mod_person = revision.person

    def update_commit_graphs (self):
        now = datetime.datetime.utcnow ()
        thisweek = blip.utils.weeknum ()
        numweeks = 104
        i = 0
        finalrev = blip.db.Revision.select_revisions (branch=self.branch)
        finalrev = finalrev.order_by ('datetime')
        outpath = None
        try:
            finalrev = finalrev[0].ident
            stillrev = True
        except IndexError:
            finalrev = None
            stillrev = False
        while stillrev or i < 2:
            topweek = thisweek - (i * numweeks)
            revstot = blip.db.Revision.count_revisions (branch=self.branch)
            revs = blip.db.Revision.select_revisions (week_range=((topweek - numweeks + 1), topweek),
                                                      branch=self.branch)
            if stillrev:
                fname = u'commits-' + str(i) + '.png'
                of = blip.db.OutputFile.select (type=u'graphs', ident=self.branch.ident, filename=fname)
                try:
                    of = of[0]
                except IndexError:
                    of = None
                if i == 0 and of is not None:
                    if self.request.get_tool_option ('timestamps', True):
                        revcount = of.data.get ('revcount', 0)
                        weeknum = of.data.get ('weeknum', None)
                        if weeknum == thisweek:
                            rev = None
                            if revcount == revstot:
                                blip.utils.log ('Skipping commit graph for %s' % self.branch.ident)
                                return
                elif of is None:
                    of = blip.db.OutputFile (type=u'graphs', ident=self.branch.ident,
                                             filename=fname, datetime=now)
                outpath = of.get_file_path()
            else:
                of = None

            if i == 0:
                blip.utils.log ('Creating commit graphs for %s' % self.branch.ident)

            stats = [0] * numweeks
            revs = list(revs)
            for rev in revs:
                if rev.ident == finalrev:
                    stillrev = False
                idx = rev.weeknum - topweek + numweeks - 1
                stats[idx] += 1

            if i == 0:
                scorestats = stats[numweeks - 26:]
                score = blip.utils.score (scorestats)
                self.branch.score = score

                scorestats = scorestats[:-3]
                avg = int(round(sum(scorestats) / (len(scorestats) * 1.0)))
                scorestats = scorestats + [avg, avg, avg]
                old = blip.utils.score (scorestats)
                score_diff = score - old
                self.branch.score_diff = score_diff

                project = self.branch.project
                if score > project.score:
                    project.score = score
                if score_diff > project.score_diff:
                    project.score_diff = score_diff

            if of is not None:
                graph = blip.graphs.BarGraph (stats, 80, height=40)
                graph.save (of.get_file_path())

            if i == 0:
                stats0 = stats
            elif i == 1 and outpath is not None:
                graph_t = blip.graphs.BarGraph (stats + stats0, 80, height=40, tight=True)
                graph_t.save (os.path.join (os.path.dirname (outpath), 'commits-tight.png'))

            if of is not None:
                of.data['coords'] = zip (graph.get_coords(), stats,
                                         range(topweek - numweeks + 1, topweek + 1))
                if len(revs) > 0:
                    of.data['revcount'] = revstot
                of.data['weeknum'] = topweek

            i += 1


    def set_default_child (self):
        default_child = None

        applications = self._children.get ('Application', [])
        applets = self._children.get ('Applet', [])
        capplets = self._children.get ('Capplet', [])
        if len(applications) == 1 and len(applets) == 0:
            default_child = applications[0]
        elif len(applets) == 1 and len(applications) == 0:
            default_child = applets[0]
        elif len(applications) > 0:
            for app in applications:
                if app.data.get ('exec', None) == self.branch.scm_module:
                    default_child = app
                    break
        elif len(applets) > 0:
            pass
        elif len(capplets) == 1:
            default_child = capplets[0]

        if default_child is not None:
            self.branch.name = default_child.name
            self.branch.desc = default_child.desc
            self.branch.icon_dir = default_child.icon_dir
            self.branch.icon_name = default_child.icon_name
            if default_child.data.has_key ('screenshot'):
                self.branch.data['screenshot'] = default_child.data['screenshot']
        else:
            self.branch.extend({
                    'name': self.branch.scm_module,
                    'desc': u'',
                    'icon_dir': None,
                    'icon_name': None,
                    })
