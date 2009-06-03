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

import codecs
from datetime import datetime, timedelta
import time
import HTMLParser
import math
import os
import os.path
import random
import sys
import tempfile
import urllib

import pulse.config


def get_token ():
    return u'%x' % random.randint (16**32, 16**33 - 1)


def utf8dec (s):
    if isinstance(s, str):
        return codecs.getdecoder('utf-8')(s, 'replace')[0]
    else:
        return s


# Just a dummy until we hook up gettext
def gettext (msg):
    """
    Return a translated string
    """
    return msg


def parse_date (datestr):
    """
    Parse a date in the format yyyy-mm-dd hh:mm::ss.
    """
    dt = datetime (*time.strptime(datestr[:19], '%Y-%m-%d %H:%M:%S')[:6])
    off = datestr[20:25]
    offhours = int(off[:3])
    offmins = int(off[0] + off[3:])
    delta = timedelta (hours=offhours, minutes=offmins)
    return dt - delta


def daynum (when=datetime.now()):
    """
    Return the number of days since the epoch for a given date
    """
    return (when - datetime(1970, 1, 1, 0, 0, 0)).days


epoch_week = datetime(1970, 1, 5, 0, 0, 0)
def weeknum (dt=None):
    """
    Return the number of weeks since the epoch for a given date
    """
    if dt == None:
        dt = datetime.utcnow()
    return ((dt - epoch_week).days // 7) + 1


def weeknumday (num):
    """
    Return the the first day of the givin week number
    """
    return (epoch_week + timedelta(days=7*(num-1)))


def tmpfile ():
    """
    Return the location of a temporary file
    """
    if not os.path.exists (pulse.config.tmp_dir):
        os.makedirs (pulse.config.tmp_dir)
    return tempfile.mkstemp (dir=pulse.config.tmp_dir)[1]


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
        elif isinstance (attr, int):
            return obj.__getitem__ (attr)
        elif len(attr) > 0:
            return attrget (attrget (obj, attr[0]), attr[1:])
        elif isinstance (obj, basestring):
            return obj.lower()
        else:
            return obj

    def lcmp (val1, val2):
        """Compare two objects, case-insensitive if strings"""
        if isinstance (val1, unicode):
            v1 = val1.lower()
        elif isinstance (val1, basestring):
            v1 = val1.decode('utf-8').lower()
        else:
            v1 = val1
        if isinstance (val2, unicode):
            v2 = val2.lower()
        elif isinstance (val1, basestring):
            v2 = val2.decode('utf-8').lower()
        else:
            v2 = val2
        return cmp (v1, v2)

    def attrcmp (val1, val2, attrs):
        """Compare two objects based on some attributes"""
        attr = attrs[0]
        try:
            attrf = attr[0]
        except:
            attrf = None
        if attrf == '-':
            attr = attr[1:]
            cmpval = lcmp (attrget(val2, attr), attrget(val1, attr))
        else:
            cmpval = lcmp (attrget(val1, attr), attrget(val2, attr))
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


class TitleParser (HTMLParser.HTMLParser):
    def __init__ (self):
        self.intitle = False
        self.title = ''
        self.done = False
        HTMLParser.HTMLParser.__init__ (self)

    def handle_starttag (self, tag, attrs):
        if tag == 'title':
            self.intitle = True

    def handle_data (self, data):
        if self.intitle:
            self.title += data

    def handle_endtag (self, tag):
        if tag == 'title':
            self.intitle = False
            self.done = True


def get_html_title (url):
    parser = TitleParser ()
    try:
        fd = urllib.urlopen (url)
    except: # XXX
        warn('Could not load url "%s"' % url)
        return None
    for line in fd:
        parser.feed (line)
        if parser.done:
            fd.close()
            return parser.title
    return None


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


class Logger (object):
    def __init__ (self):
        self.log_level = 'log'
        self.log_file = sys.stdout

    def set_log_level (self, level):
        self.log_level = level

    def set_log_file (self, filename):
        if filename is not None:
            self.log_file = file (filename, 'w')
        else:
            self.log_file = sys.stdout

    def log (self, msg):
        """Write a log message"""
        if self.log_level == 'log':
            self.log_write ('[%s] %s\n' % (datetime.now().strftime ('%Y-%m-%d %H:%M:%S'), msg))

    def warn (self, msg):
        """Write a warning message"""
        if self.log_level in ('warn', 'log'):
            self.log_write ('[%s] %s\n' % (datetime.now().strftime ('%Y-%m-%d %H:%M:%S'), msg))

    def log_write (self, str):
        if isinstance(str, unicode):
            str = str.encode('UTF-8')
        self.log_file.write (str)
        self.log_file.flush ()

logger = Logger ()

def set_log_level (level):
    logger.set_log_level (level)

def set_log_file (filename):
    logger.set_log_file (filename)

def log (msg):
    logger.log (msg)

def warn (msg):
    logger.log (msg)

def log_write (str):
    logger.log_write (str)


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
