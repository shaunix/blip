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
import blip.scm
import blip.sweep
import blip.utils

import blip.plugins.queue.sweep
import blip.plugins.scores.sweep

class ModulesResponder (blip.sweep.SweepResponder,
                        blip.plugins.queue.sweep.QueueHandler,
                        blip.plugins.scores.sweep.ScoreUpdater):
    command = 'modules'
    synopsis = 'update information about projects and module branches'

    @classmethod
    def set_usage (cls, request):
        request.set_usage ('%prog [common options] modules [command options] [ident]')

    @classmethod
    def add_tool_options (cls, request):
        request.add_tool_option ('--time-limit',
                                 dest='time_limit',
                                 metavar='SECONDS',
                                 help='process the queue for at most SECONDS seconds')
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
        request.add_tool_option ('--until',
                                 dest='until',
                                 metavar='SECONDS',
                                 help='only process modules older than SECONDS seconds')

    @classmethod
    def respond (cls, request):
        response = blip.sweep.SweepResponse (request)
        argv = request.get_tool_args ()

        dbargs = []
        until = request.get_tool_option ('until')
        if until is not None:
            sep = until.rfind (':')
            tlhour = tlmin = tlsec = 0
            if sep >= 0:
                tlsec = int(until[sep+1:])
                tlpre = until[:sep]
                sep = tlpre.rfind (':')
                if sep >= 0:
                    tlmin = int(tlpre[sep+1:])
                    tlhour = int(tlpre[:sep])
                else:
                    tlmin = int(tlpre)
            else:
                tlsec = int(until)
            until = 3600 * tlhour + 60 * tlmin + tlsec
            then = datetime.datetime.utcnow() - datetime.timedelta(seconds=int(until))
            dbargs.append (blip.db.Or (blip.db.Branch.updated < then, blip.db.Branch.updated == None))

        timelimit = request.get_tool_option ('time_limit')
        if timelimit is not None:
            sep = timelimit.rfind (':')
            tlhour = tlmin = tlsec = 0
            if sep >= 0:
                tlsec = int(timelimit[sep+1:])
                tlpre = timelimit[:sep]
                sep = tlpre.rfind (':')
                if sep >= 0:
                    tlmin = int(tlpre[sep+1:])
                    tlhour = int(tlpre[:sep])
                else:
                    tlmin = int(tlpre)
            else:
                tlsec = int(timelimit)
            timelimit = 3600 * tlhour + 60 * tlmin + tlsec
        timestart = datetime.datetime.now()

        branches = []
        if len(argv) == 0:
            branches = list(blip.db.Branch.select (blip.db.Branch.type == u'Module', *dbargs))
        else:
            for arg in argv:
                ident = blip.utils.utf8dec (arg)
                if ident.startswith(u'/set/'):
                    branches += list(blip.db.Branch.select (blip.db.Branch.type == u'Module',
                                                            blip.db.Branch.ident == blip.db.SetModule.pred_ident,
                                                            blip.db.SetModule.subj_ident.like (ident),
                                                            *dbargs))
                else:
                    branches += list(blip.db.Branch.select (blip.db.Branch.type == u'Module',
                                                            blip.db.Branch.ident.like (ident),
                                                            *dbargs))
        branches = blinq.utils.attrsorted (branches, 'updated')
        ident_i = 0
        for branch in branches:
            try:
                scanner = ModuleScanner (request, branch)
                scanner.update ()
                blip.db.flush ()
                ident_i += 1
            except Exception, err:
                blip.db.rollback ()
                blip.utils.warn (str(err))
            else:
                blip.db.commit ()

            if (timelimit is not None and
                (datetime.datetime.now() - timestart).seconds > timelimit):
                break;

        if timelimit is not None:
            diff = datetime.datetime.now () - timestart
            diff = datetime.timedelta (days=diff.days, seconds=diff.seconds)
            blip.utils.log ('Processed %i records in %s' % (ident_i, diff))

        return response

    @classmethod
    def update_scores (cls, request, ident):
        if ident is not None:
            mods = list(blip.db.Branch.select (blip.db.Branch.type == u'Module',
                                               blip.db.Branch.ident.like (ident),
                                               blip.db.Branch.score > 0))
        else:
            mods = list(blip.db.Branch.select (blip.db.Branch.type == u'Module',
                                               blip.db.Branch.score > 0))
        for mod in mods:
            blip.utils.log ('Updating score for ' + mod.ident)
            ModuleScanner.update_score (mod)

    @classmethod
    def process_queued (cls, ident, request):
        if ident.startswith (u'/mod/'):
            if ident.count('/') == 3:
                mods = list(blip.db.Branch.select (project_ident=ident))
            else:
                mods = list(blip.db.Branch.select (ident=ident))
            for mod in mods:
                try:
                    scanner = ModuleScanner (request, mod)
                    scanner.update ()
                    blip.db.flush ()
                except:
                    blip.db.rollback ()
                    raise
                else:
                    blip.db.commit ()


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
                blip.utils.warn ('Could not create instance of ' + cls.__name__)
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
        if self.repository.error is None:
            blip.db.Error.clear_error (self.branch)
        else:
            blip.db.Error.set_error (self.branch, self.repository.error)

        if self.request.get_tool_option ('read_history', True):
            self.check_history ()

        ModuleScanner.update_score (self.branch)

        # Don't even bother walking files if the repository has the same
        # revision as last time. This cuts down on disk I/O. Note that
        # some repositories don't implement get_revision, so we wrap it
        # in a try/except.
        dovisit = True
        try:
            reprev = self.repository.get_revision()[0]
        except:
            reprev = None
        if reprev is not None and self.request.get_tool_option ('timestamps'):
            currev = self.branch.data.get ('current_revision')
            if currev == reprev:
                dovisit = False

        if dovisit:
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

            self.branch.data['current_revision'] = reprev
        else:
            blip.utils.log ('Skipping file scanning for %s' % self.branch.ident)

        self.branch.updated = datetime.datetime.utcnow ()
        blip.db.Queue.pop (self.branch.ident)

    @classmethod
    def update_score (cls, branch):
        store = blip.db.get_store (blip.db.Revision)
        thisweek = blip.utils.weeknum()
        sel = store.using (blip.db.Revision,
                           blip.db.Join (blip.db.RevisionBranch,
                                         blip.db.RevisionBranch.revision_ident == blip.db.Revision.ident))
        sel = sel.find ((blip.db.Revision.weeknum, blip.db.Count('*')),
                        blip.db.And (blip.db.RevisionBranch.branch_ident == branch.ident,
                                     blip.db.Revision.weeknum > thisweek - 26,
                                     blip.db.Revision.weeknum <= thisweek))
        sel = sel.group_by (blip.db.Revision.weeknum)
        stats = [0 for i in range(26)]
        for week, cnt in list(sel):
            stats[week - (thisweek - 25)] = cnt
        branch.score = blip.utils.score (stats)

        stats = stats[:-3]
        avg = int(round(sum(stats) / (len(stats) * 1.0)))
        stats = stats + [avg, avg, avg]
        old = blip.utils.score (stats)
        branch.score_diff = branch.score - old

        scores = store.find ((blip.db.Branch.score, blip.db.Branch.score_diff),
                             blip.db.Branch.project_ident == branch.project_ident)
        scores = max (scores, key=lambda x: x[0])
        branch.project.score = scores[0]
        branch.project.score_diff = scores[1]

    def check_history (self):
        since = blip.db.Revision.get_last_revision (branch=self.branch)
        if since is not None:
            since = since.revision
            try:
                # If get_revision isn't implemented (CVS), we can't fast-path skip
                current = self.repository.get_revision()
                if current is not None and since == current[0]:
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
            rev = blip.db.Revision.select_one(ident=revident)
            if rev is None:
                rev = {'ident': revident,
                       'project_ident': self.branch.project.ident,
                       'person_ident': person.ident,
                       'revision': commit.id,
                       'datetime': commit.datetime,
                       'comment': commit.comment }
                if person.ident != commit.author_ident:
                    rev['person_alias_ident'] = commit.author_ident
                rev = blip.db.Revision (**rev)
                rev.decache ()
                for filename, filerev, prevrev in commit.files:
                    revfile = rev.add_file (filename, filerev, prevrev)
                    revfile.decache ()
            rev.add_branch (self.branch)
            blip.db.flush()

        blip.db.Revision.flush_file_cache ()
        revision = blip.db.Revision.get_last_revision (branch=self.branch)
        if revision is not None:
            self.branch.mod_datetime = revision.datetime
            self.branch.mod_person = revision.person
