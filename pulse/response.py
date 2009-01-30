# -*- coding: utf-8 -*-
# Copyright (c) 2008  Shaun McCance  <shaunm@gnome.org>
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

import cgi
import Cookie
import sys

import pulse.config

class HttpResponse (object):
    def __init__ (self, **kw):
        super (HttpResponse, self).__init__ (**kw)
        self.http_content_type = 'Content-type: text/html; charset=utf-8'
        self.http_status = 200
        self._account = None
        self._http = kw.get ('http', True)
        self._contents = None
        self._location = None
        self._cookies = []

    def redirect (self, location):
        self.http_status = 301
        self._location = location
        self._contents = None

    def get_account (self):
        return self._account

    def set_account (self, account):
        self._acount = account

    def set_contents (self, contents):
        self._contents = contents
        self._status = contents.http_status or self._status
        self._content_type = contents.http_content_type or self._content_type

    def set_cookie (self, cookie, value):
        self._cookies.append ((cookie, value))

    def output (self, fd=None):
        """Output the HTML."""
        if self._http:
            if self.http_status == 404:
                p (fd, 'Status: 404 Not found')
            elif self.http_status == 500:
                p (fd, 'Status: 500 Internal server error')
            if self.http_status == 301:
                p (fd, 'Status: 301 Moved permanently')
                p (fd, 'Location: %s' % (self._location or pulse.config.web_root))
            else:
                p (fd, 'Content-type: %s' % self.http_content_type)
            if len(self._cookies) > 0:
                ck = Cookie.SimpleCookie()
                for cookie, value in self._cookies:
                    ck[cookie] = value
                    # FIXME: this sucks.  let's change the way we keep stuff in config
                    nohttp = pulse.config.web_root
                    nohttp = nohttp[nohttp.find('://') + 3:]
                    ck[cookie]['domain'] = nohttp[:nohttp.find('/')]
                    ck[cookie]['path'] = nohttp[nohttp.find('/'):]
                p (fd, ck.output())
            p (fd, '')
        if self._contents != None:
            self._contents.output (fd=fd)


class HttpWidget (object):
    def __init__ (self, **kw):
        super (HttpWidget, self).__init__ (**kw)
        self.http_content_type = 'Content-type: text/html; charset=utf-8'
        self.http_status = 200

    def output (self, fd=None):
        pass


################################################################################
## Utility Functions

def p (fd, obj, arg=None, newline=True):
    """
    Generalized thing printer.

    This function is used to print widgets, components, and plain old strings
    in a consistent manner that avoids littering the rest of the code with a
    bunch of conditionals.

    A widget or component can be printed by passing it in as the obj argument,
    or by passing None for obj and passing the object in as the arg argument.

    If obj is a string and arg is None, obj is simply printed.  If arg is not
    None, it is interpolated in, except all substituted values are escaped to
    be safe for HTML.  Note that obj itself is not escaped, since that is used
    to print the actual HTML.  If obj is None, it is treated as "%s".

    String printing can suppress a trailing newline by passing in False for
    the newline argument.
    """
    if fd == None:
        fd = sys.stdout
    if isinstance (obj, HttpWidget):
        obj.output (fd=fd)
    elif obj == None and isinstance (arg, HttpWidget):
        arg.output (fd=fd)
    else:
        if obj == None:
            outstr = esc(arg)
        elif arg == None:
            outstr = obj
        else:
            outstr = obj % esc(arg)
        if newline:
            outstr += '\n'
        try:
            fd.write(outstr.encode('utf-8'))
        except:
            fd.write(outstr)

def esc (obj):
    """
    Make some object safe for HTML output.

    This function works on everything you can put on the right-hand side of
    an interpolation.  Strings are simply escaped, tuples have their elements
    escaped, and dictionaries are wrapped with escdict.
    """
    if isinstance (obj, unicode):
        return cgi.escape (obj, True).encode('utf-8')
    elif isinstance (obj, basestring):
        return cgi.escape (obj, True)
    elif isinstance (obj, tuple):
        return tuple (map (esc, obj))
    elif isinstance (obj, dict):
        return escdict (obj)
    else:
        return obj

class escdict (dict):
    """
    A dictionary wrapper that HTML escaped its values.
    """
    def __init__ (self, *args):
        dict.__init__ (self, *args)

    def __getitem__ (self, key):
        """Get the value for key, HTML escaped."""
        return esc (dict.__getitem__ (self, key))