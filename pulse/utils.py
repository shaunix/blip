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

from datetime import datetime
import os.path
import re
import sys

import ConfigParser

# Just a dummy until we hook up gettext
def gettext (str):
    return str

def isorted (list):
    return sorted (list, lambda x, y: cmp (x.lower(), y.lower()))

def attrsorted (list, *attrs):
    def get (obj, attrs):
        if len(attrs) > 0:
            return get (getattr (obj, attrs[0]), attrs[1:])
        elif isinstance (obj, basestring):
            return obj.lower()
        else:
            return obj
    return sorted (list, lambda x, y: cmp (get(x, attrs), get(y, attrs)))

def relative_path (path, base):
    spath = os.path.abspath (path).split (os.sep)
    sbase = os.path.abspath (base).split (os.sep)

    while len(spath) > 0 and len(sbase) > 0 and spath[0] == sbase[0]:
        spath.pop(0)
        sbase.pop(0)

    newpath = ([os.pardir] * len(sbase)) + spath
    return os.path.join (*newpath)

class odict (dict):
    def __init__ (self, d=None):
        if d != None:
            dict.__init__ (self, d)
            self._keys = d.keys()
        else:
            dict.__init__ (self)
            self._keys = []
    def __setitem__ (self, key, item):
        dict.__setitem__ (self, key, item)
        if key not in self._keys: self._keys.append (key)
    def __delitem__ (self, key):
        dict.__delitem__ (self, key)
        self._keys.remove (key)
    def keys(self):
        return self._keys
    def values (self):
        return map (lambda key: self[key], self._keys)
    def setdefault (self, key, item):
        if key not in self._keys: self.__setitem__ (key, item)

class attrdict (dict):
    def __init__ (self, objs):
        self.adds = {}
        self.dels = set()
        self.objs = objs
    def __setitem__ (self, key, item):
        self.adds[key] = item
        if key in self.dels:
            self.dels.remove (key)
    def __delitem__ (self, key):
        self.dels.add (key)
    def __getitem__ (self, key):
        if key in self.dels:
            raise KeyError (key)
        if self.adds.has_key (key):
            return self.adds[key]
        for obj in self.objs:
            try:
                ret = getattr (obj, key)
            except:
                continue
            return ret
        raise KeyError (key)
    def has_key (self, key):
        if key in self.dels:
            return False
        if self.adds.has_key (key):
            return True
        for obj in self.objs:
            try:
                getattr (obj, key)
                return True
            except:
                pass
        return False
    def has_val (self, key):
        if key in self.dels:
            return False
        if self.adds.has_key (key):
            return (self.adds[key] != None)
        for obj in self.objs:
            try:
                v = getattr (obj, key)
                return (v != None)
            except:
                pass
        return False
    def append (self, obj):
        self.objs.append (obj)
    def prepend (self, obj):
        self.objs.insert (0, obj)
    def remove (self, obj):
        self.objs.remove (obj)

class makefile (object):
    def __init__ (self, fd):
        self._variables = {}
        self._lines = []
        line = fd.readline ()
        regexp = re.compile ('''([A-Za-z_]+)(\s*=)(.*)''')
        while line:
            match = regexp.match (line)
            if match:
                varname = match.group(1)
                vartxt = match.group(3).strip()
                if vartxt.endswith ('\\'):
                    vartxt = vartxt[:-1]
                    line = fd.readline ()
                    while line:
                        vartxt += line.strip()
                        if vartxt.endswith ('\\'):
                            vartxt = vartxt[:-1]
                        else:
                            break
                        line = fd.readline()
                self._variables[varname] = vartxt
                self._lines.append (match.group(1) + match.group(2) + vartxt)
            else:
                self._lines.append (line.strip())

            if line:
                line = fd.readline ()

    def get_lines (self):
        return self._lines

    def __getitem__ (self, key):
        return self._variables[key]

    def has_key (self, key):
        return self._variables.has_key (key)

class keyfile (object):
    def __init__ (self, fd):
        cfg = ConfigParser.ConfigParser()
        cfg.optionxform = str
        cfg.readfp (fd)
        self._data = {}
        for group in cfg.sections ():
            self._data[group] = {}
            for key, value in cfg.items (group):
                lb = key.find ('[')
                rb = key.find (']')
                if lb >= 0 and rb > lb:
                    keybase = key[0:lb]
                    keylang = key[lb+1:rb]
                    self._data[group].setdefault (keybase, {})
                    if isinstance (self._data[group][keybase], basestring):
                        self._data[group][keybase] = {'C' : self._data[group][keybase]}
                    self._data[group][keybase][keylang] = value
                else:
                    self._data[group][key] = value

    def get_groups (self):
        return self._data.keys()

    def has_group (self, group):
        return self._data.has_key (group)

    def get_keys (self, group):
        return self._data[group].keys()

    def has_key (self, group, key):
        return self._data[group].has_key (key)

    def get_value (self, group, key):
        return self._data[group][key]

class PulseException (Exception):
    def __init__ (self, str):
        Exception.__init__ (self, str)

def log (str, fd=sys.stdout):
    print >>fd, '[%s] %s' % (datetime.now().strftime ('%Y-%m-%d %H:%M:%S'), str)
def warn (str, fd=sys.stderr):
    print >>fd, '[%s] %s' % (datetime.now().strftime ('%Y-%m-%d %H:%M:%S'), str)

def import_ (name):
    mod = __import__ (name)
    for c in name.split ('.')[1:]:
        mod = getattr (mod, c)
    return mod
