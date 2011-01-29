# Copyright (c) 2006-2011  Shaun McCance  <shaunm@gnome.org>
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
Read information from a Bzr repository.
"""

import codecs
import datetime
import os
import sys

import blip.scm

try:
    from email.utils import parseaddr
except:
    from email.Utils import parseaddr


class BzrBranch (blip.scm.Repository):
    """
    Clone of a Bzr repository.
    """

    scm_type = 'bzr'
    scm_branch = 'trunk'

    # FIXME
    def __init__ (self, **kw):
        blip.scm.Repository.__init__ (self, **kw)

        self.ignoredir = '.bzr'

        self._bzr_url = self.scm_server
        if self._bzr_url[-1] != '/':
            self._bzr_url += '/'
        if getattr (self, 'scm_path', None) is not None:
            self._bzr_url += self.scm_path
        else:
            self._bzr_url += self.scm_module

        blip.scm.Repository.initialize (self, **kw)


    def get_location (self, scm_dir=None, scm_file=None):
        """
        Get the location of a resource in a Bzr repository, in display form.
        """
        if scm_dir is None:
            ret = self._bzr_url
        elif scm_file is None:
            ret = '%s%s/%s' % (self._bzr_url, scm_dir)
        else:
            ret = '%s%s/%s' % (self._bzr_url, scm_dir, scm_file)
        return ret
    location = property (get_location)


    @property
    def server_name (self):
        """
        Get the name of a Bzr server, as used in an ident.
        """
        lst = self.scm_server.split('://')[1].split('/')
        if len(lst) > 1 and lst[1].startswith ('~'):
            return lst[0] + lst[1]
        else:
            return lst[0]


    def get_checkout_command (self):
        """
        Get the command to branch the Bzr repository from the server.
        """
        return 'bzr branch %s %s' % (self._bzr_url, self.scm_branch)


    def get_update_command (self):
        """
        Get the command to update the Bzr repository from the server.
        """
        return 'bzr pull'


    def get_revision (self):
        """
        Get the current revision for a Bzr repository.
        """
        owd = os.getcwd ()
        revid = revdate = None
        try:
            os.chdir (self.directory)
            cmd = 'bzr log -r-1 --show-ids'
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            for line in fd:
                if line.startswith ('revision-id:'):
                    revid = line[len('revision-id:'):].strip()
                elif line.startswith ('timestamp:'):
                    revdate = line[len('timestamp:'):].strip()
                    revdate = BzrBranch.parse_date (revdate)
        finally:
            os.chdir (owd)
        return (revid, revdate)

    def read_history (self, since=None):
        """
        Read the history of a Bzr repository.
        """
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            cmd = 'bzr log --show-ids --verbose'
            if since != None:
                cmd += ' -r"%s"..' % since
            allrevs = []
            revsdict = {}
            revid = parid = revdate = author_email = author_name = comment = None
            in_message = in_files = False
            files = []
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            for line in fd:
                if line.startswith('----'):
                    if revid is not None:
                        allrevs.insert (0, revid)
                        revsdict[revid] = (parid, revdate, author_email, author_name, comment, files)
                    revid = parid = revdate = author_email = author_name = comment = None
                    in_message = in_files = False
                    files = []
                    continue
                if line.startswith('revision-id:'):
                    revid = line[len('revision-id:'):].strip()
                    continue
                if line.startswith('parent:'):
                    parid = line[len('parent:'):].strip()
                    continue
                if line.startswith('committer:'):
                    author = line[len('committer:'):].strip()
                    author_name, author_email = parseaddr (author)
                    continue
                if line.startswith('timestamp:'):
                    revdate = line[len('timestamp:'):].strip()
                    revdate = BzrBranch.parse_date (revdate)
                    continue
                if line.startswith('message:'):
                    in_message = True
                    in_files = False
                    continue
                if line.startswith('added:') or line.startswith('removed:') or line.startswith('modified:'):
                    in_message = False
                    in_files = True
                    continue
                if in_message:
                    if comment is None:
                        comment = ''
                    else:
                        comment += '\n'
                    comment += line.strip()
                    continue
                if in_files:
                    ix = line.rfind(' ')
                    fname = line[:ix].strip()
                    files.append(fname)
                    continue
            if revid is not None:
                allrevs.insert (0, revid)
                revsdict[revid] = (parid, revdate, author_email, author_name, comment, files)
            for revid in allrevs:
                if revid == since:
                    continue
                parid, revdate, author_email, author_name, comment, files = revsdict[revid]
                revfiles = []
                for revfile in files:
                    revfiles.append ((revfile, revid, parid))
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
        Parse a date in the format given by Bzr.
        """
        revdate = datestr.split(' ', 1)[1]
        return blip.utils.parse_date (revdate)
