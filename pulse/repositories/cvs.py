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
Read information from a CVS repository.
"""

import codecs
import datetime
import os
import time

import pulse.repositories.common as scm

class CvsCheckout (scm.Checkout):
    """
    Checkout of a CVS repository.
    """

    scm_type = 'cvs'

    def __init__ (self, **kw):
        if kw.get ('scm_branch') is None:
            kw['scm_branch'] = u'HEAD'
        scm.Checkout.__init__ (self, **kw)

        self.ignoredir = 'CVS'

        scm.Checkout.initialize (self, **kw)


    def get_location (self, scm_dir=None, scm_file=None):
        """
        Get the location of a resource in a CVS repository, in display form.
        """
        ret = '%s %s' % (self.scm_server, self.scm_module)
        if self.scm_branch != 'HEAD':
            ret = '%s (%s)' % (ret, self.scm_branch)
        if scm_dir is not None:
            ret = '%s %s' % (ret, scm_dir)
            if scm_file is not None:
                ret = '%s/%s' % (ret, scm_file)
        return ret


    @property
    def server_name (self):
        """
        Get the name of a CVS server, as used in an ident.
        """
        name = self.scm_server.split(':')[2]
        if name.find ('@') >= 0:
            return name.split('@')[-1]
        else:
            return name


    def get_checkout_command (self):
        """
        Get the command to check out the CVS repository from the server.
        """
        return 'cvs -z3 -d%s co -r %s -d %s %s' % (
            self.scm_server,
            self.scm_branch,
            self.scm_branch,
            self.scm_module)


    def get_update_command (self):
        """
        Get the command to update the CVS repository from the server.
        """
        return 'cvs -z3 up -Pd'


    def get_file_revision (self, filename):
        """
        Get the revision of a file in a CVS repository.
        """
        entries = os.path.join (self.directory, os.path.dirname (filename), 'CVS', 'Entries')
        for line in open(entries):
            if line.startswith ('/' + os.path.basename (filename) + '/'):
                revnumber, revdate = line.split('/')[2:4]
                datelist = [0, 0, 0, 0, 0, 0]
                revdate = revdate.split()
                datelist[0] = int(revdate[-1])
                datelist[1] = scm.months[revdate[1]]
                datelist[2] = int(revdate[2])
                datelist[3:6] = map (int, revdate[3].split(':'))
                return (revnumber, datetime.datetime(*datelist))
        return None


    def read_history (self, since=None):
        """
        Read the history of a CVS repository.
        """
        sep = '---------------------\n'
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            cmd = 'cvsps -q -u -b ' + self.scm_branch
            if since != None:
                cmd += ' -s ' + since + '-'
            cmd += ' 2>/dev/null'
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            line = fd.readline()
            while line:
                if not line.startswith ('PatchSet '):
                    line = fd.readline()
                    continue
                revid = line[9:].strip()
                author_id = None
                revdate = None
                comment = ''
                revfiles = []
                current = None
                blank = False
                line = fd.readline()
                while True:
                    if not line or line == sep:
                        if revid != since:
                            yield scm.Commit (self, id=revid, datetime=revdate,
                                              author_id=author_id,
                                              comment=comment,
                                              files=revfiles)
                        break
                    if current == 'Log':
                        if blank:
                            blank = False
                            if line.strip() == 'Members:':
                                current = 'Members'
                            else:
                                comment += '\n'
                        else:
                            blank = (line == '\n')
                            if not blank:
                                comment += line
                    elif current == 'Members':
                        if line.strip() != '':
                            member, revs = line.strip().split(':')
                            prevrev, filerev = revs.split('->')
                            revfiles.append ((member, filerev, prevrev))
                    elif line.startswith ('Date: '):
                        datestr = line[6:].strip()
                        dt = datetime.datetime (*time.strptime (datestr, '%Y/%m/%d %H:%M:%S')[:6])
                        revdate = dt + datetime.timedelta (seconds=time.timezone)
                    elif line.startswith ('Author: '):
                        author_id = line[8:].strip()
                    elif line.strip() == 'Log:':
                        current = 'Log'
                        blank = False
                    line = fd.readline()
        except:
            os.chdir (owd)
            raise
        os.chdir (owd)
