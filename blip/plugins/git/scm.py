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

"""
Read information from a Git repository.
"""

import codecs
import datetime
import os

try:
    from email.utils import parseaddr
except:
    from email.Utils import parseaddr

import blip
import sys


class GitClone (blip.scm.Repository):
    """
    Clone of a Git repository.
    """

    scm_type = 'git'
    scm_branch = 'master'

    def __init__ (self, **kw):
        blip.scm.Repository.__init__ (self, **kw)

        self.ignoredir = '.git'

        self._git_url = self.scm_server
        if self._git_url[-1] != '/':
            self._git_url += '/'
        if getattr (self, 'scm_path', None) is not None:
            self._git_url += self.scm_path
        else:
            self._git_url += self.scm_module
        if self._git_url[-1] != '/':
            self._git_url += '/'

        blip.Repository.initialize (self, **kw)


    def get_location (self, scm_dir=None, scm_file=None):
        """
        Get the location of a resource in a Git repository, in display form.
        """
        if scm_dir is None:
            ret = self._git_url
        elif scm_file is None:
            ret = '%s%s/%s' % (self._git_url, scm_dir)
        else:
            ret = '%s%s/%s' % (self._git_url, scm_dir, scm_file)
        if self.scm_branch != 'master':
            ret = '%s (%s)' % (ret, self.scm_branch)
        return ret
    location = property (get_location)


    @property
    def server_name (self):
        """
        Get the name of a Git server, as used in an ident.
        """
        lst = self.scm_server.split('://')[1].split('/')
        if lst[1].startswith ('~'):
            return lst[0] + lst[1]
        else:
            return lst[0]


    def get_checkout_command (self):
        """
        Get the command to clone the Git repository from the server.
        """
        return ('git clone %s %s && (cd %s && (git checkout -b %s origin/%s || git checkout %s))' %
                (self._git_url, self.scm_branch, self.scm_branch,
                 self.scm_branch, self.scm_branch, self.scm_branch))


    def get_update_command (self):
        """
        Get the command to update the Git repository from the server.
        """
        return 'git fetch origin && git rebase origin/' + self.scm_branch


    def get_revision (self):
        """
        Get the current revision for a Git repository.
        """
        owd = os.getcwd ()
        revid = revdate = None
        try:
            os.chdir (self.directory)
            cmd = 'git show --name-only --pretty="format:%H%n%ad" .'
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            line = fd.readline()
            revid = line.strip()
            line = fd.readline()
            revdate = GitClone.parse_date (line.strip())
        finally:
            os.chdir (owd)
        return (revid, revdate)


    def read_history (self, since=None):
        """
        Read the history of a Git repository.
        """
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            cmd = 'git log --pretty="format:%H %P" '
            if since != None:
                cmd += '"%s..%s"' % (since, self.scm_branch)
            else:
                cmd += '"%s"' % self.scm_branch
            allrevs = []
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            for line in fd:
                hashes = line.split()
                revid = hashes[0]
                parid = len(hashes) > 1 and hashes[1] or None
                allrevs.insert (0, (revid, parid))
            for revid, parid in allrevs:
                cmd = 'git show --name-only ' + revid
                author_email = None
                author_name = None
                revdate = None
                comment = ''
                revfiles = []
                fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
                line = fd.readline()
                while line:
                    if line.startswith ('Author: '):
                        author_name, author_email = parseaddr (line[8:].strip())
                    elif line.startswith ('Date: '):
                        revdate = line[8:].strip()
                        revdate = GitClone.parse_date (revdate)
                    elif line.strip() == '':
                        line = fd.readline()
                        blank = False
                        while line:
                            if blank:
                                if line.strip() != '' and line[0] != ' ':
                                    break
                                else:
                                    comment += '\n'
                            if line.strip() == '':
                                blank = True
                            else:
                                blank = False
                                if line.startswith ('    '):
                                    comment += line[4:]
                                else:
                                    comment += line
                            line = fd.readline()
                        while line:
                            revfiles.append ((line.strip(), revid, parid))
                            line = fd.readline()
                    if line:
                        line = fd.readline()

                yield blip.scm.Commit (self, id=revid, datetime=revdate,
                                       author_email=author_email,
                                       author_name=author_name,
                                       comment=comment,
                                       files=revfiles)
        except:
            os.chdir (owd)
            raise
        os.chdir (owd)


    @staticmethod
    def parse_date (datestr):
        """
        Parse a date in the format given by Git.
        """
        revdate = datestr.split()
        datelist = [0, 0, 0, 0, 0, 0]
        datelist[0] = int(revdate[4])
        datelist[1] = blip.scm.months[revdate[1]]
        datelist[2] = int(revdate[2])
        datelist[3:6] = map (int, revdate[3].split(':'))
        date = datetime.datetime(*datelist)
        off = revdate[-1]
        offhours = int(off[:3])
        offmins = int(off[0] + off[3:])
        delta = datetime.timedelta (hours=offhours, minutes=offmins)
        date = date - delta
        return date
