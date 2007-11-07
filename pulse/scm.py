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

import commands
import os

import pulse.config
import pulse.utils

default_branches = {
    'cvs' : 'HEAD',
    'git' : 'master',
    'svn' : 'trunk'
    }

def server_name (scm_type, scm_server):
    if scm_type == 'cvs':
        name = scm_server.split(':')[2]
        if name.find ('@') >= 0:
            return name.split('@')[-1]
        else:
            return name
    elif scm_type in ('git', 'svn'):
        return scm_server.split('://')[1].split('/')[0]
    else:
        return None

class CheckoutError (pulse.utils.PulseException):
    def __init__ (self, str):
        pulse.utils.PulseException.__init__ (self, str)

class Checkout (object):
    @classmethod
    def from_record (cls, record, **kw):
        return cls (scm_type=record.scm_type,
                    scm_server=record.scm_server,
                    scm_module=record.scm_module,
                    scm_branch=record.scm_branch,
                    scm_path=record.scm_path,
                    **kw)

    def __init__ (self, **kw):
        
        updateQ = kw.get ('update', False)
        checkoutQ = kw.get ('checkout', True)

        if not kw.has_key ('scm_type'):
            print kw.keys()
            raise CheckoutError (
                'Checkout could not determine the type of SCM server to use')

        for key in kw.keys ():
            if key[:4] == 'scm_':
                self.__setattr__ (key, kw[key])

        if hasattr (Checkout, '_init_' + self.scm_type) and self.scm_type in default_branches:
            initfunc = getattr (Checkout, '_init_' + self.scm_type)
        else:
            raise CheckoutError (
                'Checkout got unknown SCM type "%s"' % self.scm_type)

        if not hasattr(self, 'scm_branch') or self.scm_branch == None:
            self.scm_branch = default_branches.get(self.scm_type)

        self._name = '%s (%s)' % (self.scm_module, self.scm_branch)

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
            if updateQ:
                self.update ()
        else:
            if checkoutQ:
                self.checkout ()

    def _init_cvs (self):
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module')
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for ' % self.scm_module)

        self.ignoredir = 'CVS'

        if self.scm_branch == 'HEAD':
            self._location = self.scm_server + ' ' + self.scm_module
        else:
            self._location = self.scm_server + ' ' + self.scm_module + '@' + self.scm_branch
        self._location_dir = self._location + ' %s'
        self._location_dirfile = self._location_dir + '/%s'
        self._co = 'cvs -z3 -d%s co -r %s -d %s %s' %(
            self.scm_server,
            self.scm_branch,
            self.scm_branch,
            self.scm_module)
        self._up = 'cvs -z3 up -Pd'

    def _init_git (self):
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module')
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for ' + self.scm_module)

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
        self._co = ('git clone --depth 0 %s %s && (cd %s && git checkout origin/%s)' %
                    (url, self.scm_branch, self.scm_branch, self.scm_branch))
        self._up = 'git fetch origin && git rebase origin/' + self.scm_branch

    def _init_svn (self):
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module')
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for ' + self.scm_module)

        self.ignoredir = '.svn'

        if self.scm_server[-1] != '/':
            self.scm_server = self.scm_server + '/'

        if getattr (self, 'scm_path', None) != None:
            url = self.scm_server + self.scm_path
        elif self.scm_branch == 'trunk':
            url = self.scm_server + self.scm_module + '/trunk'
        else:
            url = self.scm_server + self.scm_module + '/branches/' + self.scm_branch

        self._location = url
        self._location_dir = url + '/%s'
        self._location_dirfile = url + '/%s/%s'
        self._co = 'svn co ' + url + ' ' + self.scm_branch
        self._up = 'svn up'
        
    directory = property (lambda self: os.path.join (pulse.config.scmdir,
                                                     self._server_dir,
                                                     self._module_dir,
                                                     self._branch_dir))

    def get_location (self, scm_dir=None, scm_file=None):
        if scm_dir == None:
            return self._location
        elif scm_file == None:
            return self._location_dir % scm_dir
        else:
            return self._location_dirfile % (scm_dir, scm_file)

    location = property (get_location)

    def checkout (self):
        pulse.utils.log ('Checking out %s from %s' % (self._name, self._server_dir))
        topdir = os.path.join (pulse.config.scmdir, self._server_dir, self._module_dir)
        if not os.path.exists (topdir):
            os.makedirs (topdir)
        owd = os.getcwd ()
        try:
            os.chdir (topdir)
            (status, output) = commands.getstatusoutput (self._co)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)
        
    def update (self):
        pulse.utils.log ('Updating %s from %s' % (self._name, self._server_dir))
        owd = os.getcwd ()
        try:
            os.chdir (self.directory)
            (status, output) = commands.getstatusoutput (self._up)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)
