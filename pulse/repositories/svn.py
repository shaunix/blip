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

"""
Read information from an SVN repository.
"""

import codecs
import os

from pulse import utils

import pulse.repositories.common as scm

class SvnCheckout (scm.Checkout):
    """
    Checkout of an SVN repository.
    """

    scm_type = 'svn'

    def __init__ (self, **kw):
        if kw.get ('scm_branch') is None:
            kw['scm_branch'] = u'trunk'
        scm.Checkout.__init__ (self, **kw)

        self.ignoredir = '.svn'

        self._svn_url = self.scm_server
        if self._svn_url[-1] != '/':
            self._svn_url += '/'
        if getattr (self, 'scm_path', None) is not None:
            self._svn_url += self.scm_path
        elif self.scm_branch == 'trunk':
            self._svn_url += self.scm_module + '/trunk/'
        else:
            self._svn_url += '%s/branches/%s/' % (self.scm_module, self.scm_branch)
        if self._svn_url[-1] != '/':
            self._svn_url += '/'

        scm.Checkout.initialize (self, **kw)


    def get_location (self, scm_dir=None, scm_file=None):
        """
        Get the location of a resource in an SVN repository, in display form.
        """
        if scm_dir is None:
            return self._svn_url
        elif scm_file is None:
            return '%s%s/%s' % (self._svn_url, scm_dir)
        else:
            return '%s%s/%s' % (self._svn_url, scm_dir, scm_file)

    @property
    def server_name (self):
        """
        Get the name of an SVN server, as used in an ident.
        """
        lst = self.scm_server.split('://')[1].split('/')
        if lst[1].startswith ('~'):
            return lst[0] + lst[1]
        else:
            return lst[0]

    def get_checkout_command (self):
        """
        Get the command to check out the SVN repository from the server.
        """
        return 'svn co ' + self._svn_url + ' ' + self.scm_branch


    def get_update_command (self):
        """
        Get the command to update the SVN repository from the server.
        """
        return 'svn up'
        

    def get_revision (self):
        """
        Get the current revision for an SVN repository.
        """
        owd = os.getcwd ()
        retval = None
        try:
            os.chdir (self.directory)
            cmd = 'svn info .'
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            revnumber = revdate = None
            for line in fd:
                if line.startswith ('Last Changed Rev: '):
                    revnumber = line[18:].strip()
                elif line.startswith ('Last Changed Date: '):
                    revdate = line[19:].strip()
                    break
            if revnumber != None and revdate != None:
                retval = (revnumber, SvnCheckout.parse_date (revdate))
        finally:
            os.chdir (owd)
        if retval != None:
            return retval


    def read_history (self, since=None):
        """
        Read the history of an SVN repository.
        """
        sep = '-' * 72 + '\n'
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            fd = codecs.getreader('utf-8')(os.popen ('svn info'), errors='replace')
            for line in fd:
                if line.startswith ('Repository Root:'):
                    svnroot = line[16:].strip()
                    break
            cmd = 'svn log -v'
            if since != None:
                cmd += ' -r' + since + ':HEAD'
            else:
                # Since the beginning of time, to give us oldest first
                cmd += ' -r\'{1970-01-01}\':HEAD'
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            line = fd.readline()
            while line:
                line = fd.readline()
                if not line:
                    break
                onbranch = False
                (revid, author_id, revdate) = line.split('|')[:3]
                revid = revid[1:].strip()
                prevrev = str(int(revid) - 1)
                author_id = author_id.strip ()
                revdate = SvnCheckout.parse_date (revdate)
                comment = ''
                revfiles = []
                line = fd.readline()
                if line.strip() == 'Changed paths:':
                    line = fd.readline()
                    while line:
                        if line == '\n' or line == sep:
                            break
                        filename = line.strip()[3:]
                        fullfilename = svnroot + u'/' + filename
                        if fullfilename.startswith (self._svn_url):
                            onbranch = True
                            filename = fullfilename[len(self._svn_url)+1:]
                        else:
                            filename = u'/' + filename
                        i = filename.find ('(from ')
                        if i >= 0:
                            filename = filename[:i]
                        filename = filename.strip()
                        if filename == '':
                            filename = u'.'
                        # FIXME: if I knew how to get the previous revision that
                        # affected this file, I would.  But I don't know how to
                        # get that from the single svn log command, and I'm not
                        # about to do extra svn calls for each revision.
                        revfiles.append ((filename, revid, prevrev))
                        line = fd.readline()
                if line == '\n':
                    line = fd.readline()
                while line:
                    if line == sep:
                        break
                    comment += line
                    line = fd.readline()
                if revid != since:
                    if onbranch:
                        yield scm.Commit (self, id=revid, datetime=revdate,
                                          author_id=author_id,
                                          comment=comment,
                                          files=revfiles)
            else:
                line = fd.readline()
        except:
            os.chdir (owd)
            raise
        os.chdir (owd)


    @staticmethod
    def parse_date (datestr):
        """
        Parse a date in the format given by SVN.
        """
        return utils.parse_date (datestr.split('(')[0].strip())
