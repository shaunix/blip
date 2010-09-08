# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
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
from urlparse import urlsplit

def get_token ():
    """
    Return a random token for authentication
    """
    return u'%x' % random.randint (16**32, 16**33 - 1)

def read_subclasses (cls):
    for subcls in cls.__subclasses__():
        yield subcls
        for subsub in read_subclasses (subcls):
            yield subsub


def utf8dec (s):
    """
    Decode a string to UTF-8, or don't if it already is
    """
    if isinstance(s, str):
        return codecs.getdecoder('utf-8')(s, 'replace')[0]
    else:
        return s

def utf8enc (s):
    """
    Encode a unicode object to UTF-8, or don't if it already is
    """
    if isinstance(s, unicode):
        return codecs.getencoder('utf-8')(s)[0]
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


#def tmpfile ():
#    """
#    Return the location of a temporary file
#    """
#    if not os.path.exists (pulse.config.tmp_dir):
#        os.makedirs (pulse.config.tmp_dir)
#    return tempfile.mkstemp (dir=pulse.config.tmp_dir)[1]


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


class BlipException (Exception):
    """Base class for exceptions that Blip raises"""
    def __init__ (self, msg):
        Exception.__init__ (self, msg)


# unquote, parse_qs and parse_qsl are taken from python2.6 module "urlparse"
_hextochr = dict(('%02x' % i, chr(i)) for i in range(256))
_hextochr.update(('%02X' % i, chr(i)) for i in range(256))
def unquote(s):
    """unquote('abc%20def') -> 'abc def'."""
    res = s.split('%')
    for i in xrange(1, len(res)):
        item = res[i]
        try:
            res[i] = _hextochr[item[:2]] + item[2:]
        except KeyError:
            res[i] = '%' + item
        except UnicodeDecodeError:
            res[i] = unichr(int(item[:2], 16)) + item[2:]
    return "".join(res)

def parse_qs(qs, keep_blank_values=0, strict_parsing=0):
    """Parse a query given as a string argument.

        Arguments:

        qs: URL-encoded query string to be parsed

        keep_blank_values: flag indicating whether blank values in
            URL encoded queries should be treated as blank strings.
            A true value indicates that blanks should be retained as
            blank strings.  The default false value indicates that
            blank values are to be ignored and treated as if they were
            not included.

        strict_parsing: flag indicating what to do with parsing errors.
            If false (the default), errors are silently ignored.
            If true, errors raise a ValueError exception.
    """
    dict = {}
    for name, value in parse_qsl(qs, keep_blank_values, strict_parsing):
        if name in dict:
            dict[name].append(value)
        else:
            dict[name] = [value]
    return dict

def parse_qsl(qs, keep_blank_values=0, strict_parsing=0):
    """Parse a query given as a string argument.

    Arguments:

    qs: URL-encoded query string to be parsed

    keep_blank_values: flag indicating whether blank values in
        URL encoded queries should be treated as blank strings.  A
        true value indicates that blanks should be retained as blank
        strings.  The default false value indicates that blank values
        are to be ignored and treated as if they were  not included.

    strict_parsing: flag indicating what to do with parsing errors. If
        false (the default), errors are silently ignored. If true,
        errors raise a ValueError exception.

    Returns a list, as G-d intended.
    """
    pairs = [s2 for s1 in qs.split('&') for s2 in s1.split(';')]
    r = []
    for name_value in pairs:
        if not name_value and not strict_parsing:
            continue
        nv = name_value.split('=', 1)
        if len(nv) != 2:
            if strict_parsing:
                raise ValueError, "bad query field: %r" % (name_value,)
            # Handle case of a control-name with no equal sign
            if keep_blank_values:
                nv.append('')
            else:
                continue
        if len(nv[1]) or keep_blank_values:
            name = unquote(nv[0].replace('+', ' '))
            value = unquote(nv[1].replace('+', ' '))
            r.append((name, value))

    return r

class URL(object):
    """
    URL representing object. You can manipulate it by editing
    scheme, netloc, path and query of an instance.
    """
    def __init__(self, scheme='http', netloc='example.org', path='', query={}, fragment=''):
        self.scheme = scheme
        self.netloc = netloc
        self.path = path
        if isinstance(query, basestring):
            query = parse_qs(query)
        self.query = query
        self.fragment = fragment

    @classmethod
    def from_str(self, string):
        """Creates an URL object from a string.
        
            May u be an URL object than:
            u == URL.from_str(str(u))"""
        return URL(*urlsplit(string))

    def __str__(self):
        query = urllib.urlencode(self.query, True)
        if query != '':
            query = '?' + query
        return '%s://%s%s%s' % (self.scheme, self.netloc, self.path, query)

    def __setitem__(self, attr, value):
        self.query[attr] = value

    def __getitem__(self, attr):
        return self.query[attr]

    def _set_path(self, path):
        """Make sure path starts with a /"""
        if not path[0] == '/':
            path = '/' + path
        self._path = path
    path = property(lambda self: self._path, _set_path)


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

def language_name (lang):
    if lang == 'af':
       return gettext ('Afrikaans')
    elif lang == 'am':
       return gettext ('Amharic')
    elif lang == 'an':
       return gettext ('Aragonese')
    elif lang == 'ang':
       return gettext ('Old English')
    elif lang == 'ar':
       return gettext ('Arabic')
    elif lang == 'as':
       return gettext ('Assamese')
    elif lang == 'ast':
       return gettext ('Asturian')
    elif lang == 'az':
       return gettext ('Azerbaijani')
    elif lang == 'az_IR':
       return gettext ('Azerbaijani (Iranian)')
    elif lang == 'bal':
       return gettext ('Balochi')
    elif lang == 'be':
       return gettext ('Belarusian')
    elif lang == 'bem':
       return gettext ('Bemba')
    elif lang == 'bg':
       return gettext ('Bulgarian')
    elif lang == 'bn':
       return gettext ('Bengali')
    elif lang == 'bn_IN':
       return gettext ('Bengali (India)')
    elif lang == 'br':
       return gettext ('Breton')
    elif lang == 'bs':
       return gettext ('Bosnian')
    elif lang == 'ca':
       return gettext ('Catalan')
    elif lang == 'crh':
       return gettext ('Crimean Tatar')
    elif lang == 'cs':
       return gettext ('Czech')
    elif lang == 'cy':
       return gettext ('Welsh')
    elif lang == 'da':
       return gettext ('Danish')
    elif lang == 'de':
       return gettext ('German')
    elif lang == 'dv':
       return gettext ('Divehi')
    elif lang == 'dz':
       return gettext ('Dzongkha')
    elif lang == 'el':
       return gettext ('Greek')
    elif lang == 'en@shaw':
       return gettext ('Shavian')
    elif lang == 'en_AU':
       return gettext ('English (Australian)')
    elif lang == 'en_CA':
       return gettext ('English (Canadian)')
    elif lang == 'en_GB':
       return gettext ('English (British)')
    elif lang == 'eo':
       return gettext ('Esperanto')
    elif lang == 'es':
       return gettext ('Spanish')
    elif lang == 'et':
       return gettext ('Estonian')
    elif lang == 'eu':
       return gettext ('Basque')
    elif lang == 'fa':
       return gettext ('Persian')
    elif lang == 'ff':
       return gettext ('Fula')
    elif lang == 'fi':
       return gettext ('Finnish')
    elif lang == 'fr':
       return gettext ('French')
    elif lang == 'fur':
       return gettext ('Friulian')
    elif lang == 'fy':
       return gettext ('Frisian')
    elif lang == 'ga':
       return gettext ('Irish')
    elif lang == 'gl':
       return gettext ('Galician')
    elif lang == 'gn':
       return gettext ('Guarani')
    elif lang == 'gu':
       return gettext ('Gujarati')
    elif lang == 'gv':
       return gettext ('Manx')
    elif lang == 'ha':
       return gettext ('Hausa')
    elif lang == 'he':
       return gettext ('Hebrew')
    elif lang == 'hi':
       return gettext ('Hindi')
    elif lang == 'hr':
       return gettext ('Croatian')
    elif lang == 'hu':
       return gettext ('Hungarian')
    elif lang == 'hy':
       return gettext ('Armenian')
    elif lang == 'id':
       return gettext ('Indonesian')
    elif lang == 'io':
       return gettext ('Ido')
    elif lang == 'is':
       return gettext ('Icelandic')
    elif lang == 'it':
       return gettext ('Italian')
    elif lang == 'ja':
       return gettext ('Japanese')
    elif lang == 'ka':
       return gettext ('Georgian')
    elif lang == 'kk':
       return gettext ('Kazakh')
    elif lang == 'km':
       return gettext ('Khmer')
    elif lang == 'kn':
       return gettext ('Kannada')
    elif lang == 'ko':
       return gettext ('Korean')
    elif lang == 'ks':
       return gettext ('Kashmiri')
    elif lang == 'ku':
       return gettext ('Kurdish')
    elif lang == 'ky':
       return gettext ('Kirghiz')
    elif lang == 'la':
       return gettext ('Latin')
    elif lang == 'li':
       return gettext ('Limburgian')
    elif lang == 'lo':
       return gettext ('Lao')
    elif lang == 'lt':
       return gettext ('Lithuanian')
    elif lang == 'lv':
       return gettext ('Latvian')
    elif lang == 'mai':
       return gettext ('Maithili')
    elif lang == 'mg':
       return gettext ('Malagasy')
    elif lang == 'mi':
       return gettext ('Maori')
    elif lang == 'mk':
       return gettext ('Macedonian')
    elif lang == 'ml':
       return gettext ('Malayalam')
    elif lang == 'mn':
       return gettext ('Mongolian')
    elif lang == 'mr':
       return gettext ('Marathi')
    elif lang == 'ms':
       return gettext ('Malay')
    elif lang == 'my':
       return gettext ('Burmese')
    elif lang == 'nap':
       return gettext ('Neapolitan')
    elif lang == 'nds':
       return gettext ('Low German')
    elif lang == 'ne':
       return gettext ('Nepali')
    elif lang == 'nl':
       return gettext ('Dutch')
    elif lang == 'no':
       return gettext ('Norwegian (Bokmål and Nynorsk)')
    elif lang == 'nso':
       return gettext ('Northern Sotho')
    elif lang == 'oc':
       return gettext ('Occitan')
    elif lang == 'or':
       return gettext ('Oriya')
    elif lang == 'pa':
       return gettext ('Punjabi')
    elif lang == 'pl':
       return gettext ('Polish')
    elif lang == 'ps':
       return gettext ('Pashto')
    elif lang == 'pt':
       return gettext ('Portuguese')
    elif lang == 'pt_BR':
       return gettext ('Portuguese (Brazilian)')
    elif lang == 'ro':
       return gettext ('Romanian')
    elif lang == 'ru':
       return gettext ('Russian')
    elif lang == 'rw':
       return gettext ('Kinyarwanda')
    elif lang == 'si':
       return gettext ('Sinhala')
    elif lang == 'sk':
       return gettext ('Slovak')
    elif lang == 'sl':
       return gettext ('Slovenian')
    elif lang == 'sq':
       return gettext ('Albanian')
    elif lang == 'sr':
       return gettext ('Serbian')
    elif lang == 'sv':
       return gettext ('Swedish')
    elif lang == 'ta':
       return gettext ('Tamil')
    elif lang == 'te':
       return gettext ('Telugu')
    elif lang == 'tg':
       return gettext ('Tajik')
    elif lang == 'th':
       return gettext ('Thai')
    elif lang == 'tk':
       return gettext ('Turkmen')
    elif lang == 'tl':
       return gettext ('Tagalog')
    elif lang == 'tr':
       return gettext ('Turkish')
    elif lang == 'tt':
       return gettext ('Tatar')
    elif lang == 'ug':
       return gettext ('Uighur')
    elif lang == 'uk':
       return gettext ('Ukrainian')
    elif lang == 'ur':
       return gettext ('Urdu')
    elif lang == 'uz':
       return gettext ('Uzbek')
    elif lang == 'vi':
       return gettext ('Vietnamese')
    elif lang == 'wa':
       return gettext ('Walloon')
    elif lang == 'xh':
       return gettext ('Xhosa')
    elif lang == 'yi':
       return gettext ('Yiddish')
    elif lang == 'yo':
       return gettext ('Yoruba')
    elif lang == 'zh_CN':
       return gettext ('Chinese (China)')
    elif lang == 'zh_trad':
       return gettext ('Chinese Traditional')
    elif lang == 'zu':
       return gettext ('Zulu')
    return lang
