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

import pulse.config as config
import pulse.db as db
import pulse.utils as utils


class CheckoutError (utils.PulseException):
    def __init__ (self, str):
        utils.PulseException.__init__ (self, str)

class Checkout:
    def __init__ (self, resource, **kw):
        updateQ = kw.get ('update', False)

        # Some sanity checks
        if not isinstance (resource, db.RcsResource):
            raise CheckoutError (
                'Checkout expects an RcsResource object.')
        if not isinstance (resource.rcs_server, db.RcsServer):
            raise CheckoutError (
                'Checkout got an RcsResource without a valid RcsServer.')

        self._server = resource.rcs_server.name

        # Call the _init function for this rcsType
        if hasattr (Checkout, '_init_' + resource.rcs_server.rcs_type):
            getattr (Checkout, '_init_' + resource.rcs_server.rcs_type) (self, resource, **kw)
        else:
            raise CheckoutError (
                'Checkout got an RcsServer with an unknown type: "%s".'
                % resource.rcs_server.rcs_type)

        if os.path.exists (os.path.join (self._topdir, self._codir)):
            if updateQ:
                self.update ()
        else:
            self.checkout ()

    def _init_cvs (self, resource, **kw):
        self._name = '%s (%s)' % (resource.rcs_module, resource.rcs_branch or 'HEAD')
        self._topdir = os.path.join (config.rcsdir,
                                     resource.rcs_server.ident.split('/')[-1],
                                     resource.rcs_module)
        self._codir = resource.rcs_branch or 'HEAD'
        self._subdir = resource.rcs_dir or ''
        self._file = resource.rcs_file or ''
        self._co = 'cvs -z3 -d%s co -r %s -d %s %s' %(
            resource.rcs_server.rcs_root,
            resource.rcs_branch or 'HEAD',
            resource.rcs_branch or 'HEAD',
            resource.rcs_module)
        self._up = 'cvs -z3 up -Pd'

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
        utils.log ('Checking out %s from %s' % (self._name, self._server))
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
        utils.log ('Updating %s from %s' % (self._name, self._server))
        owd = os.getcwd ()
        try:
            os.chdir (os.path.join (self._topdir, self._codir))
            (status, output) = commands.getstatusoutput (self._up)
            # FIXME: check status, log output if error
        finally:
            os.chdir (owd)
