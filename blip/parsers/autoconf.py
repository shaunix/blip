# Copyright (c) 2007-2010  Shaun McCance  <shaunm@gnome.org>
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

import commands
import fnmatch
import os
import re

class Autoconf (object):
    """
    Parse a configure.ac file.
    """

    def __init__ (self, record, filename):
        dirname = os.path.dirname (filename)
        basename = os.path.basename (filename)
        owd = os.getcwd ()
        try:
            os.chdir (dirname)
            (status, output) = commands.getstatusoutput ('autoconf "%s" 2>/dev/null' % basename)
        finally:
            os.chdir (owd)
        if status != 256:
            output = open(filename).read()
        self._vars = {}
        self._functxts = {}
        self._funcargs = {}
        if record is not None and record.data.has_key ('configure_args'):
            for arg in record.data['configure_args'].split():
                if arg.startswith ('--with-'):
                    (var, sep, val) = arg.partition ('=')
                    var = var[2:].replace ('-', '_')
                    self._vars[var] = val
        infunc = None
        incase = False
        caseval = None
        casematch = casedone = False
        casere = re.compile ('case \"?\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?\"? in')
        condre = re.compile ('\s*([^\)]+)\)(.*)')
        varre = re.compile ('^\s*([A-Z_]+)=\'?([^\']*)\'?')
        for line in output.split('\n'):
            if incase:
                if line.strip() == 'esac':
                    incase = False
                    continue
                if casedone:
                    continue
                if not casematch and caseval is not None:
                    m = condre.match (line)
                    if m:
                        if fnmatch.fnmatch (caseval, m.group(1)):
                            casematch = True
                            line = m.group(2)
                if casematch:
                    if line.endswith(';;'):
                        casematch = False
                        casedone = True
                        line = line[:-2]
                else:
                    continue
            if infunc is None:
                if line.startswith ('AC_INIT('):
                    infunc = 'AC_INIT'
                    self._functxts[infunc] = ''
                    line = line[8:]
                elif line.startswith ('AM_INIT_AUTOMAKE('):
                    infunc = 'AM_INIT_AUTOMAKE'
                    self._functxts[infunc] = ''
                    line = line[17:]
                elif line.startswith ('AS_VERSION('):
                    infunc = 'AS_VERSION'
                    self._functxts[infunc] = ''
                    line = line[11:]
                else:
                    m = casere.match (line)
                    if m and not line.endswith ('esac'):
                        casevar = m.group(1)
                        incase = True
                        caseval = self._vars.get (casevar, None)
                        casematch = False
                        casedone = False
                        continue
                    m = varre.match (line)
                    if m:
                        varval = m.group(2).strip()
                        if len(varval) > 0 and varval[0] == varval[-1] == '"':
                            varval = varval[1:-1]
                        self._vars[m.group(1)] = self.subvar(varval)
            if infunc is not None:
                rparen = line.find (')')
                if rparen >= 0:
                    self._functxts[infunc] += line[:rparen]
                    infunc = None
                else:
                    self._functxts[infunc] += line.strip()

        for func in self._functxts.keys():
            args = []
            for arg in self._functxts.get(func).split(','):
                arg = arg.strip()
                if len(arg) > 0 and arg[0] == '[' and arg[-1] == ']':
                    arg = arg[1:-1]
                    arg = arg.strip()
                else:
                    arg = self.subvar (arg)
                args.append (arg)
            self._funcargs[func] = args

        initargs = self.get_func_args ('AC_INIT')
        if len(initargs) < 2:
            initargs = self.get_func_args('AM_INIT_AUTOMAKE')
        if len(initargs) < 2:
            initargs = ['', '']
        if self._functxts.has_key ('AS_VERSION'):
            versargs = self.get_func_args ('AS_VERSION')
            initargs[0] = versargs[0].strip()
            initargs[1] = '.'.join ([s.strip() for s in versargs[2:5]])

        pkgname = self.get_variable ('PACKAGE_TARNAME')
        if pkgname == '':
            pkgname = self.get_variable ('PACKAGE_NAME')
        if pkgname == '':
            if len(initargs) >= 4:
                pkgname = initargs[3]
            else:
                pkgname = initargs[0]
        self._pkgname = pkgname
        if not self._vars.has_key ('PACKAGE'):
            self._vars['PACKAGE'] = self._pkgname

        pkgversion = self._vars.get ('PACKAGE_VERSION', '').strip()
        if pkgversion == '':
            pkgversion = initargs[1]
        self._pkgversion = self.subvar (pkgversion)

    def subvar (self, var):
        r1 = re.compile ('(\$\{?[A-Za-z_][A-Za-z0-9_]*\}?)')
        r2 = re.compile ('\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?')
        ret = ''
        for el in r1.split(var):
            m = r2.match(el)
            if m and self._vars.has_key (m.group(1)) and self._vars[m.group(1)] != var:
                ret += self.subvar (self._vars[m.group(1)])
            else:
                ret += el
        return ret

    def get_variable (self, var, default=''):
        return self.subvar (self._vars.get(var, default)).strip()

    def get_func_args (self, func):
        return self._funcargs.get(func, [])

    def get_package_name (self):
        return self._pkgname

    def get_package_version (self):
        return self._pkgversion
