# -*- coding: utf-8 -*-
# Copyright (c) 2008-2010  Shaun McCance  <shaunm@gnome.org>
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

import cgi
import Cookie
import os
import sys

import blip.config
import blip.core
import blip.utils


class WebException (blip.utils.BlipException):
    def __init__ (self, title, desc):
        self.title = title
        self.desc = desc


class WebRequest (blip.core.Request):
    def __init__ (self, **kw):
        super (WebRequest, self).__init__ (**kw)

        self.path_info = kw.get ('path_info', os.getenv ('PATH_INFO'))
        self.query_string = kw.get ('query_string', os.getenv ('QUERY_STRING'))

        self.path = []
        if self.path_info is not None:
            path = blip.utils.utf8dec (self.path_info).split ('/')
            for part in path:
                if part != '':
                    self.path.append (part)

        self.query = {}
        if self.query_string is not None:
            query = cgi.parse_qs (self.query_string, True)
            for key in query.keys():
                self.query[key] = blip.utils.utf8dec (query[key][0])

        self.cookies = Cookie.SimpleCookie ()
        self.cookies.load(kw.get('http_cookie', os.getenv ('HTTP_COOKIE') or ''))

        self.http = kw.get ('http', True)


class WebResponse (blip.core.Response):
    def __init__ (self, request, **kw):
        super (WebResponse, self).__init__ (request, **kw)
        self.http_login = None
        self.http_account = None
        self.http_content_type = 'text/html; charset=utf-8'
        self.http_content_disposition = None
        self.http_status = 200
        self._widget = None
        self._location = None
        self._cookies = []

    def get_return_code (self):
        if self.http_status in (200, 301):
            return 0
        else:
            return self.http_status

    def redirect (self, location):
        self.http_status = 301
        self._location = location
        self._widget = None

    def set_widget (self, widget):
        self._widget = widget
        self.http_status = widget.http_status or self.http_status
        self.http_content_type = widget.http_content_type or self.http_content_type

    def set_cookie (self, cookie, value):
        self._cookies.append ((cookie, value))

    def output (self, fd=None):
        """Output the HTML."""
        self._fd = fd
        if self._fd is None:
            self._fd = sys.stdout
        if self.request.http:
            if self.http_status == 404:
                self.out ('Status: 404 Not found')
            elif self.http_status == 500:
                self.out ('Status: 500 Internal server error')
            if self.http_status == 301:
                self.out ('Status: 301 Moved permanently')
                self.out ('Location: %s' % (self._location or config.web_uri))
            else:
                self.out ('Content-type: %s' % self.http_content_type)
                if self.http_content_disposition is not None:
                    self.out ('Content-disposition: %s' % self.http_content_disposition)
            if len(self._cookies) > 0:
                ck = Cookie.SimpleCookie()
                for cookie, value in self._cookies:
                    ck[cookie] = value
                    nohttp = config.web_uri
                    nohttp = nohttp[nohttp.find('://') + 3:]
                    ck[cookie]['domain'] = nohttp[:nohttp.find('/')]
                    ck[cookie]['path'] = nohttp[nohttp.find('/'):]
                self.out (ck.output())
            self.out ('')
        if self._widget is not None:
            self._widget.output (self)

    def out (self, obj, arg=None, newline=True):
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
        if isinstance (obj, WebWidget):
            obj.output (self)
        elif obj == None and isinstance (arg, WebWidget):
            arg.output (self)
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
                self._fd.write (outstr.encode('utf-8'))
            except:
                self._fd.write (outstr)


class WebResponder (blip.core.Responder):
    @classmethod
    def respond (cls, request, **kw):
        try:
            blip.core.import_plugins ('web')
            if request.query.has_key ('q'):
                responderbase = ContentResponder
            elif request.query.has_key ('d'):
                responderbase = DataResponder
            else:
                responderbase = PageResponder
            for responder in responderbase.get_extensions ():
                response = responder.respond (request)
                if response is not None:
                    break
            if response is None:
                raise blip.utils.BlipException ('No responder found')
        except Exception, err:
            if not request.http:
                raise
            if request.query.has_key ('q') or request.query.has_key ('d'):
                page = blip.html.AdmonBox (
                    blip.html.AdmonBox.error,
                    blip.utils.gettext (
                        'Blip does not know how to construct this page.  This is' +
                        ' probably because some naughty little monkeys didn\'t finish' +
                        ' their programming assignment.'))
            else:
                page = blip.html.PageError (blip.utils.gettext (
                    'Blip does not know how to construct this page.  This is' +
                    ' probably because some naughty little monkeys didn\'t finish' +
                    ' their programming assignment.'))
            response = WebResponse (request)
            response.set_widget (page)

        return response

################################################################################
        
class PageResponder (blip.core.Responder):
    pass

class ContentResponder (blip.core.Responder):
    pass

class DataResponder (blip.core.Responder):
    pass

################################################################################

class WebWidget (object):
    def __init__ (self, **kw):
        self.http_content_type = 'text/html; charset=utf-8'
        self.http_response = None
        self.http_status = 200

    def output (self, response):
        raise NotImplementedError ('%s does not provide the output method.'
                                   % self.__class__.__name__)

################################################################################

class WebTextWidget (WebWidget):
    def __init__ (self, **kw):
        super (WebTextWidget, self).__init__ (**kw)
        self.http_content_type = 'text/plain; charset=utf-8'
        self._content = []

    def add_text_content (self, content):
        self._content.append (content)

    def output (self, res):
        for line in self._content:
            res.out (line, None, False)

################################################################################

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
