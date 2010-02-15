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
Read information from a source code repository.
"""

import commands
import os

import blip.config
import blip.core
import blip.utils

months = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6,
          'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}


class RepositoryError (blip.utils.BlipException):
    """
    An error in reading from a source code repository.
    """
    def __init__ (self, msg):
        blip.utils.BlipException.__init__ (self, msg)


class Commit (object):
    """
    A commit in a repository, as yielded by Repository.read_history.
    """
    def __init__ (self, repository, **kw):
        self.repository = repository
        self.id = blip.utils.utf8dec (kw.get ('id'))
        self.datetime = kw.get ('datetime')
        self.author_id = blip.utils.utf8dec (kw.get ('author_id'))
        self.author_email = blip.utils.utf8dec (kw.get ('author_email'))
        self.author_name = blip.utils.utf8dec (kw.get ('author_name'))
        self.comment = blip.utils.utf8dec (kw.get ('comment'))
        self.files = kw.get ('files', [])

    @property
    def author_ident (self):
        """
        Get the ident for the author of this commit.
        """
        if self.author_id is not None:
            return u'/person/%s@%s' % (self.author_id, self.repository.server_name)
        elif self.author_email is not None:
            return u'/person/' + self.author_email
        else:
            return u'/ghost/' + self.author_name
        

class Repository (blip.core.ExtensionPoint):
    """
    Checkout or clone of a source code repository.
    """
    scm_type = None
    scm_branch = None

    _cached_repos = {}

    def __new__(cls, *args, **kw):
        if cls == Repository and 'scm_type' in kw:
            subcls = Repository.get_repository_class (kw['scm_type'])
        if subcls is None:
            raise RepositoryError (blip.utils.gettext ('No plugin found for %s repositories') % kw['scm_type'])
        repoid = ':::'.join ([kw.get('scm_type') or '__none__',
                              kw.get('scm_server') or '__none__',
                              kw.get('scm_module') or '__none__',
                              kw.get('scm_path') or '__none__',
                              kw.get('scm_branch') or subcls.scm_branch])
        if cls._cached_repos.has_key (repoid):
            return cls._cached_repos[repoid]
        obj = object.__new__(subcls)
        obj._initialized = False
        cls._cached_repos[repoid] = obj
        return obj

    @staticmethod
    def get_default_branch (scm_type):
        for subcls in Repository.get_extensions ():
            if subcls.scm_type == scm_type:
                return subcls.scm_branch
        return None

    @classmethod
    def get_repository_class (cls, scm_type):
        for subcls in cls.get_extensions ():
            if subcls.scm_type == scm_type:
                return subcls
        return None

    @classmethod
    def from_record (cls, record, **kw):
        """
        Get a Repository from the information in a database record.
        """
        return Repository (scm_type=record.scm_type,
                           scm_server=record.scm_server,
                           scm_module=record.scm_module,
                           scm_branch=record.scm_branch,
                           scm_path=record.scm_path,
                           **kw)
    

    @property
    def server_name (self):
        """
        Get the name of a repository server, as used in an ident.
        """
        raise NotImplementedError ('%s does not implement the server_name property.'
                                   % self.__class__.__name__)

    @property
    def directory (self):
        """
        Get the directory of the checkout on the local filesystem.
        """
        return os.path.join (blip.config.scm_dir, self.server_dir, self.module_dir, self.branch_dir)


    def __init__ (self, **kw):
        self.scm_type = kw.get ('scm_type')
        self.scm_server = kw.get ('scm_server')
        self.scm_module = kw.get ('scm_module')
        self.scm_branch = kw.get ('scm_branch')
        self.scm_path = kw.get ('scm_path')

        if self.scm_module is None:
            raise RepositoryError ('Repository did not receive a module.')
        if self.scm_server is None:
            raise RepositoryError ('Repository did not receive a server for %s.'
                                   % self.scm_module)
        if self.scm_branch is None:
            self.scm_branch = self.__class__.scm_branch
        if self.scm_branch is None:
            raise RepositoryError ('Repository did not receive a branch for %s.'
                                   % self.scm_module)

        self.error = None
        self.ignoredir = None

        self.server_dir = kw.get ('server_dir', self.server_name)
        self.module_dir = kw.get ('module_dir', self.scm_module)
        self.branch_dir = kw.get ('branch_dir', self.scm_branch)


    def initialize (self, **kw):
        """
        Perform an update or checkout on __init__.
        """
        if self._initialized:
            return
        self._initialized = True
        if os.path.exists (self.directory):
            if kw.get ('update', False):
                self.update ()
        else:
            if kw.get ('checkout', True):
                self.checkout ()


    def get_location (self, scm_dir=None, scm_file=None):
        """
        Get the location of a resource in a repository, in display form.
        """
        raise NotImplementedError ('%s does not implement the get_location method.'
                                   % self.__class__.__name__)
    location = property (get_location)


    def get_checkout_command (self):
        """
        Get the command to check out the repository from the server.
        """
        return None


    def checkout (self):
        """
        Check out or clone the repository from the server.
        """
        cmd = self.get_checkout_command ()
        if cmd is None:
            raise NotImplementedError ('%s does not implement the checkout method.'
                                       % self.__class__.__name__)
        blip.utils.log ('Checking out %s (%s) from %s'
                        % (self.scm_module, self.scm_branch, self.server_dir))
        topdir = os.path.join (blip.config.scm_dir, self.server_dir, self.module_dir)
        if not os.path.exists (topdir):
            os.makedirs (topdir)
        owd = os.getcwd ()
        try:
            os.chdir (topdir)
            (status, output) = commands.getstatusoutput (cmd)
            if status != 0:
                blip.utils.warn (
                    'Failed to check out %s (%s) from %s with command\n                      %s'
                    % (self.scm_module, self.scm_branch, self.server_dir, cmd))
                self.error = output.split('\n')[-1]
        finally:
            os.chdir (owd)
        

    def get_update_command (self):
        """
        Get the command to update the repository from the server.
        """
        return None


    def update (self):
        """
        Update the repository from the server.
        """
        cmd = self.get_update_command ()
        if cmd is None:
            raise NotImplementedError ('%s does not implement the update method.'
                                       % self.__class__.__name__)
        blip.utils.log ('Updating %s (%s) from %s'
                        % (self.scm_module, self.scm_branch, self.server_dir))
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            (status, output) = commands.getstatusoutput (cmd)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)


    def get_revision (self):
        """
        Get the current revision for a repository.
        """
        raise NotImplementedError ('%s does not implement the get_revision method.'
                                   % self.__class__.__name__)


    def read_history (self, since=None):
        """
        Read the history of a source code repository.

        You can optionally pass in a revision to read the history since.
        This function is an iterator, and will yeild dictionaries with
        information about each revision.
        """
        raise NotImplementedError ('%s does not implement the read_history method.'
                                   % self.__class__.__name__)


# Load all repository modules.  This must happen after everything else, so that
# Repository and Commit are defined, since the scm plugins rely on these.  Also,
# Python doesn't set the parent module's attribute for this module until it's
# done importing.  So if we try to import blip.scm in a plugin, we'll get this:
#   AttributeError: 'module' object has no attribute 'scm'
# To work around this, we explicitly set blip.scm to this module before we
# import the plugins.  See this bug report:
#   http://bugs.python.org/issue992389
import blip
import sys
blip.scm = sys.modules[__name__]
blip.core.import_plugins ('scm')
