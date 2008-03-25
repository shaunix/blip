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

"""Various utility functions"""

from datetime import datetime
import math
import os.path
import sys


# Just a dummy until we hook up gettext
def gettext (msg):
    """
    Return a translated string
    """
    return msg


def daynum (when=datetime.now()):
    """
    Return the number of days since the epoch for a given date
    """
    return (when - datetime(1970, 1, 1, 0, 0, 0)).days


epoch_week = datetime(1970, 1, 5, 0, 0, 0)
def weeknum (dt):
    """
    Return the number of weeks since the epoch for a given date
    """
    return ((dt - epoch_week).days // 7) + 1


def score (stats):
    """
    Calculate the score for a list of statistics

    The score associated with a list is a weighted sum of the values,
    where earlier values are weighted down as the square root of their
    distance from the end of the list.
    """
    ret = 0
    den = math.sqrt (len(stats))
    for i in range(len(stats)):
        ret += (math.sqrt(i + 1) / den) * stats[i]
    return int(ret)


def split (things, num):
    """
    Split a list into num sublists

    This function is used to split lists into sublists, trying to minimize
    the difference between lengths of sublists.  Instead of just returning
    a list of sublists, it returns an interator which yields tuples with
    a list item, which sublist that item belongs to, and the position of
    that item in the sublist.
    """
    each = len(things) // num
    ext = len(things) % num
    idx = i = start = 0
    while start < len(things):
        end = start + each + (i < ext)
        for j in range(start, end):
            yield (things[j], idx, j - start)
        start = end
        i += 1
        idx += 1


def isorted (lst):
    """
    Perform a case-insensitive lexicographic sort
    """
    return sorted (lst, lambda x, y: cmp (x.lower(), y.lower()))


def attrsorted (lst, *attrs):
    """
    Sort a list of objects based on given object attributes

    The list is first sorted by comparing the value of the first attribute
    for each object.  When the values for two objects are equal, they are
    sorted according to the second attribute, third attribute, and so on.

    An attribute may also be a tuple or list.  In this case, the value to
    be compared for an object is obtained by successively extracting the
    attributes.  For example, an attribute of ('foo', 'bar') would use the
    value of obj.foo.bar for the object obj.

    All string comparisons are case-insensitive.
    """
    def attrget (obj, attr):
        """Get an attribute or list of attributes from an object"""
        if isinstance (attr, basestring):
            return getattr (obj, attr)
        elif len(attr) > 0:
            return attrget (getattr (obj, attr[0]), attr[1:])
        elif isinstance (obj, basestring):
            return obj.lower()
        else:
            return obj

    def lcmp (val1, val2):
        """Compare two objects, case-insensitive if strings"""
        return cmp (isinstance(val1, basestring) and val1.lower() or val1,
                    isinstance(val2, basestring) and val2.lower() or val2)

    def attrcmp (val1, val2, attrs):
        """Compare two objects based on some attributes"""
        cmpval = lcmp (attrget(val1, attrs[0]), attrget(val2, attrs[0]))
        if cmpval == 0 and len(attrs) > 1:
            return attrcmp (val1, val2, attrs[1:])
        else:
            return cmpval

    return sorted (lst, lambda val1, val2: attrcmp (val1, val2, attrs))


def relative_path (path, base):
    """
    Return path relative to base
    """
    spath = os.path.abspath (path).split (os.sep)
    sbase = os.path.abspath (base).split (os.sep)

    while len(spath) > 0 and len(sbase) > 0 and spath[0] == sbase[0]:
        spath.pop(0)
        sbase.pop(0)

    newpath = ([os.pardir] * len(sbase)) + spath
    return os.path.join (*newpath)


def xmliter (node):
    """
    An iterator for libxml2 child nodes
    """
    child = node.children
    while child:
        yield child
        child = child.next


class odict (dict):
    """
    An ordered dictionary

    Things placed in an odict are returned in the order they were inserted.
    """

    def __init__ (self, mapping=None):
        if mapping != None:
            super (odict, self).__init__ (mapping)
            self._keys = mapping.keys()
        else:
            super (odict, self).__init__ ()
            self._keys = []

    def __setitem__ (self, key, item):
        dict.__setitem__ (self, key, item)
        if key not in self._keys:
            self._keys.append (key)

    def __delitem__ (self, key):
        dict.__delitem__ (self, key)
        self._keys.remove (key)

    def keys(self):
        """Return the keys in the order they were added"""
        return self._keys

    def values (self):
        """Return the values in the order they were added"""
        return [self[key] for key in self._keys]

    def setdefault (self, key, item):
        """Set a value only if no value has been set for the key"""
        if key not in self._keys:
            self.__setitem__ (key, item)


class PulseException (Exception):
    """Base class for exceptions that Pulse raises"""
    def __init__ (self, msg):
        Exception.__init__ (self, msg)


def log (msg, fd=sys.stdout):
    """Write a log message"""
    print >> fd, '[%s] %s' % (datetime.now().strftime ('%Y-%m-%d %H:%M:%S'), msg)

def warn (msg, fd=sys.stderr):
    """Write a warning message"""
    print >> fd, '[%s] %s' % (datetime.now().strftime ('%Y-%m-%d %H:%M:%S'), msg)


def import_ (name):
    """
    Dynamically import and return a module

    Python's built-in __import__ function returns the top-level module of
    an imported module.  For instance, __import__('foo.bar') will import
    foo.bar, but will return a reference to foo.  import_ will return a
    reference to bar.
    """
    mod = __import__ (name)
    for modname in name.split ('.')[1:]:
        mod = getattr (mod, modname)
    return mod
