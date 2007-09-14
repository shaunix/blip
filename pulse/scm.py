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


class CheckoutError (pulse.utils.PulseException):
    def __init__ (self, str):
        pulse.utils.PulseException.__init__ (self, str)

class Checkout (object):
    def __init__ (self, **kw):
        updateQ = kw.get ('update', False)

        # Some sanity checks
        if not kw.has_key ('ident'):
            raise CheckoutError(
                'Checkout did not receive an identifier')
        self.ident = kw['ident']
        
        if not kw.has_key ('scm_type'):
            raise CheckoutError (
                'Checkout could not determine the type of SCM server to use for ' % self.ident)

        for key in kw.keys ():
            if key[:4] == 'scm_':
                self.__setattr__ (key, kw[key])

        if hasattr (Checkout, '_init_' + self.scm_type):
            getattr (Checkout, '_init_' + self.scm_type) (self)
        else:
            raise CheckoutError (
                'Checkout got unknown SCM type "%s" for ' % (self.scmType, self.ident))

        if os.path.exists (os.path.join (self._topdir, self._codir)):
            if updateQ:
                self.update ()
        else:
            self.checkout ()

    def _init_cvs (self):
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for ' % self.ident)
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module for ' % self.ident)

        if not hasattr(self, 'scm_branch'):
            self.scm_branch = 'HEAD'
                
        self._name = '%s (%s)' % (self.scm_module, self.scm_branch)
        self._server = self.scm_server.split(':')[2],
        self._topdir = os.path.join (pulse.config.scmdir,
                                     self._server,
                                     self.scm_module)
        self._codir = self.scm_branch
        self._co = 'cvs -z3 -d%s co -r %s -d %s %s' %(
            self.scm_server,
            self.scm_branch,
            self.scm_branch,
            self.scm_module)
        self._up = 'cvs -z3 up -Pd'

    def _init_svn (self):
        if not hasattr (self, 'scm_server'):
            raise CheckoutError ('Checkout did not receive a server for ' % self.ident)
        if not hasattr (self, 'scm_module'):
            raise CheckoutError ('Checkout did not receive a module for ' % self.ident)

        if self.scm_server[-1] != '/':
            self.scm_server = self.scm_server + '/'
        if not hasattr(self, 'scm_branch'):
            self.scm_branch = 'trunk'

        self._name = '%s (%s)' % (self.scm_module, self.scm_branch)
        self._server = self.scm_server.split('://')[1].split('/')[0]
        self._topdir = os.path.join (pulse.config.scmdir,
                                     self._server,
                                     self.scm_module)
        self._codir = self.scm_branch
        self._co = 'svn co %s%s/%s' %(
            self.scm_server,
            self.scm_module,
            self.scm_branch
            )
        self._up = 'svn up'
        

    directory = property (lambda self: os.path.join (self._topdir,
                                                     self._codir,
                                                     self._subdir))
    def _get_file (self):
        if self._file:
            return os.path.join (self._topdir,
                                 self._codir,
                                 self._subdir,
                                 self._file)
        else:
            return None
    file = property (lambda self: self._get_file())

    def checkout (self):
        pulse.utils.log ('Checking out %s from %s' % (self._name, self._server))
        if not os.path.exists (self._topdir):
            os.makedirs (self._topdir)
        owd = os.getcwd ()
        try:
            os.chdir (self._topdir)
            (status, output) = commands.getstatusoutput (self._co)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)
        
    def update (self):
        pulse.utils.log ('Updating %s from %s' % (self._name, self._server))
        owd = os.getcwd ()
        try:
            os.chdir (os.path.join (self._topdir, self._codir))
            (status, output) = commands.getstatusoutput (self._up)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)
