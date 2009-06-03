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
Read information from a source code repository.
"""

import commands
import os

from pulse import config, utils

months = {'Jan':1, 'Feb':2, 'Mar':3, 'Apr':4, 'May':5, 'Jun':6,
          'Jul':7, 'Aug':8, 'Sep':9, 'Oct':10, 'Nov':11, 'Dec':12}


class CheckoutError (utils.PulseException):
    """
    An error in reading from a source code repository.
    """
    def __init__ (self, msg):
        utils.PulseException.__init__ (self, msg)


class Commit (object):
    """
    A commit in a repository, as yielded by Checkout.read_history.
    """
    def __init__ (self, checkout, **kw):
        self.checkout = checkout
        self.id = utils.utf8dec (kw.get ('id'))
        self.datetime = kw.get ('datetime')
        self.author_id = utils.utf8dec (kw.get ('author_id'))
        self.author_email = utils.utf8dec (kw.get ('author_email'))
        self.author_name = utils.utf8dec (kw.get ('author_name'))
        self.comment = utils.utf8dec (kw.get ('comment'))
        self.files = kw.get ('files', [])

    @property
    def author_ident (self):
        """
        Get the ident for the author of this commit.
        """
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

    def __new__(cls, *args, **kw):
        if cls == Checkout and 'scm_type'in kw:
            cls = Checkout._get_child(kw['scm_type'])
        return object.__new__(cls, *args, **kw)

    @classmethod
    def from_record (cls, record, **kw):
        """
        Get a checkout from the information in a database record.
        """
        return Checkout (scm_type=record.scm_type,
                         scm_server=record.scm_server,
                         scm_module=record.scm_module,
                         scm_branch=record.scm_branch,
                         scm_path=record.scm_path,
                         **kw)

    @classmethod
    def _get_child(cls, scm_type):
        classes = filter(lambda c: c.scm_type == scm_type, Checkout.__subclasses__())
        if not classes:
            raise NotImplementedError('No Checkout "%s" implementation available.'
                                      % scm_type)
        return classes[0]

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
        return os.path.join (config.scm_dir, self.server_dir, self.module_dir, self.branch_dir)


    def __init__ (self, **kw):
        self.scm_type = kw.get ('scm_type')
        self.scm_server = kw.get ('scm_server')
        self.scm_module = kw.get ('scm_module')
        self.scm_branch = kw.get ('scm_branch')
        self.scm_path = kw.get ('scm_path')

        if self.scm_module is None:
            raise CheckoutError ('Checkout did not receive a module.')
        if self.scm_server is None:
            raise CheckoutError ('Checkout did not receive a server for %s.'
                                 % self.scm_module)
        if self.scm_branch is None:
            self.scm_branch = self.__class__.scm_branch
        if self.scm_branch is None:
            raise CheckoutError ('Checkout did not receive a branch for %s.'
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
        utils.log ('Checking out %s (%s) from %s'
                   % (self.scm_module, self.scm_branch, self.server_dir))
        topdir = os.path.join (config.scm_dir, self.server_dir, self.module_dir)
        if not os.path.exists (topdir):
            os.makedirs (topdir)
        owd = os.getcwd ()
        try:
            os.chdir (topdir)
            (status, output) = commands.getstatusoutput (cmd)
            if status != 0:
                utils.warn (
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
        utils.log ('Updating %s (%s) from %s'
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
        raise NotImplementedError ('%s does not implement the read_revision method.'
                                   % self.__class__.__name__)



