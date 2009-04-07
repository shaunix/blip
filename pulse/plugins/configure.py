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
ModuleScanner plugin for module configuration files.
"""

import commands
import os
import re

from pulse import config, db, utils

import pulse.pulsate.modules

class ConfigureHandler (object):
    """
    ModuleScanner plugin for module configuration files.
    """

    def __init__ (self, scanner):
        self.scanner = scanner

    def process_file (self, dirname, basename, **kw):
        """
        Process a configure.in or configure.ac file.
        """
        if dirname == self.scanner.checkout.directory:
            if basename in ('configure.in', 'configure.ac'):
                self.process_configure (os.path.join (dirname, basename), **kw)

    def process_configure (self, filename, **kw):
        """
        Process a configure.in or configure.ac file.
        """
        branch = self.scanner.branch
        checkout = self.scanner.checkout

        rel_scm = utils.relative_path (filename, config.scm_dir)
        mtime = os.stat(filename).st_mtime

        if not kw.get('no_timestamps', False):
            stamp = db.Timestamp.get_timestamp (rel_scm)
            if mtime <= stamp:
                utils.log ('Skipping file %s' % rel_scm)
                return
        utils.log ('Processing file %s' % rel_scm)

        owd = os.getcwd ()
        try:
            os.chdir (checkout.directory)
            (status, output) = commands.getstatusoutput ('autoconf "%s" 2>/dev/null' % filename)
        finally:
            os.chdir (owd)
        if status != 256:
            output = open(filename).read()
        vars = {}
        functxts = {}
        infunc = None
        varre = re.compile ('^([A-Z_]+)=\'?([^\']*)\'?')
        for line in output.split('\n'):
            if infunc == None:
                if line.startswith ('AC_INIT('):
                    infunc = 'AC_INIT'
                    functxts[infunc] = ''
                    line = line[8:]
                elif line.startswith ('AM_INIT_AUTOMAKE('):
                    infunc = 'AM_INIT_AUTOMAKE'
                    functxts[infunc] = ''
                    line = line[17:]
                elif line.startswith ('AS_VERSION('):
                    infunc = 'AS_VERSION'
                    functxts[infunc] = ''
                    line = line[11:]
                else:
                    m = varre.match (line)
                    if m:
                        varval = m.group(2).strip()
                        if len(varval) > 0 and varval[0] == varval[-1] == '"':
                            varval = varval[1:-1]
                        vars[m.group(1)] = varval
            if infunc != None:
                rparen = line.find (')')
                if rparen >= 0:
                    functxts[infunc] += line[:rparen]
                    infunc = None
                else:
                    functxts[infunc] += line.strip()

        initargs = functxts.get('AC_INIT', '').split(',')
        if len(initargs) < 2:
            initargs = functxts.get('AM_INIT_AUTOMAKE', '').split(',')
        if len(initargs) < 2:
            initargs = ['', '']
        for i in range(len(initargs)):
            arg = initargs[i]
            arg = arg.strip()
            if len(arg) > 0 and arg[0] == '[' and arg[-1] == ']':
                arg = arg[1:-1]
            arg = arg.strip()
            initargs[i] = arg
        if functxts.has_key ('AS_VERSION'):
            versargs = functxts['AS_VERSION'].split(',')
            initargs[0] = versargs[0].strip()
            initargs[1] = '.'.join ([s.strip() for s in versargs[2:5]])

        def subvar (var):
            r1 = re.compile ('(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)')
            r2 = re.compile ('\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?')
            ret = ''
            for el in r1.split(var):
                m = r2.match(el)
                if m and vars.has_key (m.group(1)):
                    ret += subvar (vars[m.group(1)])
                else:
                    ret += el
            return ret

        tarname = vars.get ('PACKAGE_TARNAME', '').strip()
        if tarname == '':
            tarname = vars.get ('PACKAGE_NAME', '').strip()
        if tarname == '':
            if len(initargs) >= 4:
                tarname = initargs[3]
            else:
                tarname = initargs[0]
        tarname = subvar (tarname)

        tarversion = vars.get ('PACKAGE_VERSION', '').strip()
        if tarversion == '':
            tarversion = initargs[1]
        tarversion = subvar (tarversion)

        series = tarversion.split('.')[:2]
        try:
            minor = int (series[1])
            if minor % 2 == 1:
                minor += 1
            series[1] = str (minor)
        except:
            pass
        series = '.'.join (series)

        branch.data['PACKAGE_NAME'] = vars.get ('PACKAGE_NAME', '').strip()
        branch.data['tarname'] = tarname
        branch.data['tarversion'] = tarversion
        branch.data['series'] = series

        db.Timestamp.set_timestamp (rel_scm, mtime)

pulse.pulsate.modules.ModuleScanner.register_plugin (ConfigureHandler)
