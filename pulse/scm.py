# Copyright (c) 2006  Shaun McCance  <shaunm@gnome.org>
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
Read information from a source code repository.
"""

import commands
import codecs
import datetime
import os
import time

try:
    from email.utils import parseaddr
except:
    from email.Utils import parseaddr

import pulse.config
import pulse.utils

default_branches = {
    'cvs' : u'HEAD',
    'git' : u'master',
    'svn' : u'trunk'
    }
months = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6,
          'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}


def server_name (scm_type, scm_server):
    """
    Get a somewhat human-readable server name for a source code repository.
    """
    if scm_type == 'cvs':
        name = scm_server.split(':')[2]
        if name.find ('@') >= 0:
            return name.split('@')[-1]
        else:
            return name
    elif scm_type in ('git', 'svn'):
        lst = scm_server.split('://')[1].split('/')
        if lst[1].startswith ('~'):
            return lst[0] + lst[1]
        else:
            return lst[0]
    else:
        return None

class CheckoutError (pulse.utils.PulseException):
    """
    An error in reading from a source code repository.
    """
    def __init__ (self, msg):
        pulse.utils.PulseException.__init__ (self, msg)

class Commit (object):
    def __init__ (self, checkout, **kw):
        self.checkout = checkout
        self.id = pulse.utils.utf8dec (kw.get ('id'))
        self.datetime = kw.get ('datetime')
        self.author_id = pulse.utils.utf8dec (kw.get ('author_id'))
        self.author_email = pulse.utils.utf8dec (kw.get ('author_email'))
        self.author_name = pulse.utils.utf8dec (kw.get ('author_name'))
        self.comment = pulse.utils.utf8dec (kw.get ('comment'))
        self.files = kw.get ('files', [])

    @property
    def author_ident (self):
        if self.author_id is not None:
            return u'/person/%s@%s' % (self.author_id, self.checkout.server_name)
        elif self.author_email is not None:
            return u'/person/' + self.author_email
        else:
            return u'/ghost/' + self.author_name
        

class Checkout (object):
    """
    Checkout or clone of a source code repository.
    """

    @classmethod
    def from_record (cls, record, **kw):
        """
        Get a checkout from the information in a database record.
        """
        return cls (scm_type=record.scm_type,
                    scm_server=record.scm_server,
                    scm_module=record.scm_module,
                    scm_branch=record.scm_branch,
                    scm_path=record.scm_path,
                    **kw)

    @property
    def server_name (self):
        return server_name (self.scm_type, self.scm_server)

    def __init__ (self, **kw):
        if not kw.has_key ('scm_type'):
            raise CheckoutError (
                'Checkout could not determine the type of SCM server to use')

        self.scm_type = kw.get('scm_type')
        self.scm_server = kw.get('scm_server')
        self.scm_module = kw.get('scm_module')
        self.scm_branch = kw.get('scm_branch')
        self.scm_path = kw.get('scm_path')

        self.error = None

        if (hasattr (Checkout, '_init_' + self.scm_type) and self.scm_type in default_branches):
            initfunc = getattr (Checkout, '_init_' + self.scm_type)
        else:
            raise CheckoutError (
                'Checkout got unknown SCM type "%s"' % self.scm_type)

        if not hasattr(self, 'scm_branch') or self.scm_branch == None:
            self.scm_branch = default_branches.get(self.scm_type)

        self._name = '%s (%s)' % (self.scm_module, self.scm_branch)

        self.ignoredir = None
        self._location = None
        self._location_dir = None
        self._location_dirfile = None
        self._up = None
        self._co = None

        initfunc (self)

        if kw.get('server_dir') != None:
            self._server_dir = kw['server_dir']
        else:
            self._server_dir = server_name (self.scm_type, self.scm_server)

        if kw.get('module_dir') != None:
            self._module_dir = kw['module_dir']
        else:
            self._module_dir = self.scm_module

        if kw.get('branch_dir') != None:
            self._branch_dir = kw['branch_dir']
        else:
            self._branch_dir = self.scm_branch

        if os.path.exists (self.directory):
            if kw.get ('update', False):
                self.update ()
        else:
            if kw.get ('checkout', True):
                self.checkout ()

    def _init_cvs (self):
        """
        Initialize information for a CVS repository.
        """
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module')
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for '
                                 % self.scm_module)

        self.ignoredir = 'CVS'

        self._location = self.scm_server + ' ' + self.scm_module
        if self.scm_branch != 'HEAD':
            self._location += '@' + self.scm_branch
        self._location_dir = self._location + ' %s'
        self._location_dirfile = self._location_dir + '/%s'
        self._co = 'cvs -z3 -d%s co -r %s -d %s %s' % (
            self.scm_server,
            self.scm_branch,
            self.scm_branch,
            self.scm_module)
        self._up = 'cvs -z3 up -Pd'

    def _init_git (self):
        """
        Initialize information for a Git repository.
        """
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module')
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for '
                                 + self.scm_module)

        self.ignoredir = '.git'

        if self.scm_server[-1] != '/':
            self.scm_server = self.scm_server + '/'

        if getattr (self, 'scm_path', None) != None:
            url = self.scm_server + self.scm_path
        else:
            url = self.scm_server + self.scm_module

        if self.scm_branch == 'master':
            self._location = url
            self._location_dir = url + '/%s'
            self._location_dirfile = url + '/%s/%s'
        else:
            self._location = url + '@' + self.scm_branch
            self._location_dir = url + '/%s@' + self.scm_branch
            self._location_dirfile = url + '/%s/%s@' + self.scm_branch
        self._co = ('git clone %s %s && (cd %s && git checkout -b %s origin/%s)' %
                    (url, self.scm_branch,
                     self.scm_branch, self.scm_branch, self.scm_branch))
        self._up = 'git fetch origin && git rebase origin/' + self.scm_branch

    def _init_svn (self):
        """
        Initialize information for an SVN repository.
        """
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module')
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for '
                                 + self.scm_module)

        self.ignoredir = '.svn'

        if self.scm_server[-1] != '/':
            self.scm_server = self.scm_server + '/'

        url = self.scm_server
        if getattr (self, 'scm_path', None) != None:
            url += self.scm_path
        elif self.scm_branch == 'trunk':
            url += self.scm_module + '/trunk'
        else:
            url += self.scm_module + '/branches/' + self.scm_branch

        self._location = url
        self._location_dir = url + '/%s'
        self._location_dirfile = url + '/%s/%s'
        self._co = 'svn co ' + url + ' ' + self.scm_branch
        self._up = 'svn up'
        

    @property
    def directory (self):
        """
        Get the directory on the local filesystem of the checkout.
        """
        return os.path.join (pulse.config.scm_dir,
                             self._server_dir,
                             self._module_dir,
                             self._branch_dir)


    def get_location (self, scm_dir=None, scm_file=None):
        """
        Get the location of a resource in a source code repository.
        """
        if scm_dir == None:
            return self._location
        elif scm_file == None:
            return self._location_dir % scm_dir
        else:
            return self._location_dirfile % (scm_dir, scm_file)
    location = property (get_location)


    def checkout (self):
        """
        Check out or clone the repository from a server.
        """
        pulse.utils.log ('Checking out %s from %s'
                         % (self._name, self._server_dir))
        topdir = os.path.join (pulse.config.scm_dir,
                               self._server_dir,
                               self._module_dir)
        if not os.path.exists (topdir):
            os.makedirs (topdir)
        owd = os.getcwd ()
        try:
            os.chdir (topdir)
            (status, output) = commands.getstatusoutput (self._co)
            if status != 0:
                pulse.utils.warn (
                    'Failed to check out %s from %s with command\n                      %s'
                    % (self._name, self._server_dir, self._co))
                self.error = output.split('\n')[-1]
        finally:
            os.chdir (owd)
        

    def update (self):
        """
        Update the repository from a server.
        """
        pulse.utils.log ('Updating %s from %s' % (self._name, self._server_dir))
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            (status, output) = commands.getstatusoutput (self._up)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)


    ############################################################################

    def get_revision (self):
        """
        Get the current revision for a repository.
        """
        if (hasattr (Checkout, '_get_revision_' + self.scm_type) and
            self.scm_type in default_branches):
            func = getattr (Checkout, '_get_revision_' + self.scm_type)
        else:
            raise CheckoutError (
                'get_revision got unknown SCM type "%s"' % self.scm_type)
        return func (self)

    def _get_revision_cvs (self):
        """
        Get the current revision for a CVS repository.
        """
        # FIXME
        return None

    def _get_revision_git (self):
        """
        Get the current revision for a Git repository.
        """
        owd = os.getcwd ()
        revnumber = revdate = None
        try:
            os.chdir (self.directory)
            cmd = 'git show --name-only --pretty="format:%H%n%ad" .'
            fd = codecs.getreader('utf-8')(os.popen (cmd), errors='replace')
            line = fd.readline()
            revnumber = line.strip()
            line = fd.readline()
            revdate = parse_date_git (line.strip())
        finally:
            os.chdir (owd)
        return (revnumber, revdate)

    def _get_revision_svn (self):
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
                retval = (revnumber, parse_date_svn (revdate))
        finally:
            os.chdir (owd)
        if retval != None:
            return retval


    ############################################################################

    def _get_file_revision_cvs (self, filename):
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
                datelist[1] = months[revdate[1]]
                datelist[2] = int(revdate[2])
                datelist[3:6] = map (int, revdate[3].split(':'))
                return (revnumber, datetime.datetime(*datelist))
        return None

    ############################################################################

    def read_history (self, since=None):
        """
        Read the history of a source code repository.

        You can optionally pass in a revision to read the history since.
        This function is an iterator, and will yeild dictionaries with
        information about each revision.
        """
        if (hasattr (Checkout, '_read_history_' + self.scm_type) and
            self.scm_type in default_branches):
            func = getattr (Checkout, '_read_history_' + self.scm_type)
        else:
            raise CheckoutError (
                'read_history got unknown SCM type "%s"' % self.scm_type)
        return func (self, since=since)

    def _read_history_cvs (self, since=None):
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
                            yield Commit (self, id=revid, datetime=revdate,
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

    def _read_history_git (self, since=None):
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
                        author_email, author_name = parseaddr (line[8:].strip())
                    elif line.startswith ('Date: '):
                        revdate = line[8:].strip()
                        revdate = parse_date_git (revdate)
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

                yield Commit (self, id=revid, datetime=revdate,
                              author_email=author_email,
                              author_name=author_name,
                              comment=comment,
                              files=revfiles)
        except:
            os.chdir (owd)
            raise
        os.chdir (owd)

    def _read_history_svn (self, since=None):
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
                revdate = parse_date_svn (revdate)
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
                        if fullfilename.startswith (self._location):
                            onbranch = True
                            filename = fullfilename[len(self._location)+1:]
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
                        yield Commit (self, id=revid, datetime=revdate,
                                      author_id=author_id,
                                      comment=comment,
                                      files=revfiles)
            else:
                line = fd.readline()
        except:
            os.chdir (owd)
            raise
        os.chdir (owd)


def parse_date (datestr):
    """
    Parse a date in the format yyyy-mm-dd hh:mm::ss.
    """
    dt = datetime.datetime (*time.strptime(datestr[:19], '%Y-%m-%d %H:%M:%S')[:6])
    off = datestr[20:25]
    offhours = int(off[:3])
    offmins = int(off[0] + off[3:])
    delta = datetime.timedelta (hours=offhours, minutes=offmins)
    return dt - delta

def parse_date_svn (datestr):
    """
    Parse a date in the format given by SVN.
    """
    return parse_date (datestr.split('(')[0].strip())

def parse_date_git (datestr):
    """
    Parse a date in the format given by Git.
    """
    revdate = datestr.split()
    datelist = [0, 0, 0, 0, 0, 0]
    datelist[0] = int(revdate[4])
    datelist[1] = months[revdate[1]]
    datelist[2] = int(revdate[2])
    datelist[3:6] = map (int, revdate[3].split(':'))
    date = datetime.datetime(*datelist)
    off = revdate[-1]
    offhours = int(off[:3])
    offmins = int(off[0] + off[3:])
    delta = datetime.timedelta (hours=offhours, minutes=offmins)
    date = date - delta
    return date

