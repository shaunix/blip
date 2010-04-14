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

import blinq.config
import blinq.ext
import blinq.reqs.web

import blip.utils


class WebRequest (blinq.reqs.web.WebRequest):
    def __init__ (self, **kw):
        super (WebRequest, self).__init__ (**kw)
        self.record = None
        self.account = None
        self.account_locator = None


class WebResponse (blinq.reqs.web.WebResponse):
    def __init__ (self, request, **kw):
        super (WebResponse, self).__init__ (request, **kw)


class WebResponder (blinq.reqs.Responder):
    @classmethod
    def respond (cls, request):
        try:
            import blip.plugins
            blinq.ext.import_extensions (blip.plugins, 'web')

            # First, let an AccountHandler set request.account.  This could
            # be based on a login cookie, but it might not for e.g. HTTP
            # authentication.  We do this first because everything after
            # this could change its behavior based on whether the user is
            # logged in.  We also disable any account handler except the
            # active one, because account handlers are usually header
            # links providers
            try:
                account_handler = blinq.config.account_handler
            except:
                account_handler = 'basic'
            handler = None
            for ext in AccountHandler.get_extensions ():
                if handler is not None:
                    blinq.ext.ExtensionPoint.disable_extension (ext)
                elif ext.account_handler == account_handler:
                    handler = ext
                    handler.locate_account (request)
                else:
                    blinq.ext.ExtensionPoint.disable_extension (ext)

            # The AccountHandler gets to handle everything that starts with
            # /account.  If the handler wants to enable plugins to provide
            # additional subpages, then it should provide its own extension
            # points.  Note that handler might still be None, but we're not
            # doing anything except the standard error page, so we just let
            # the try/except clause take care of it.
            if len(request.path) != 0 and request.path[0] == 'account':
                response = handler.respond (request)
                if response is None:
                    raise blip.utils.BlipException ('No responder found')
                return response

            # Next, let a RecordLocator set request.record based on request.
            # Usually, this involves matching PATH_INFO against an ident, but
            # locate_record returns a boolean, so record locators can claim
            # they've located something even when there's no database entry.
            locator = None
            for loc in RecordLocator.get_extensions ():
                if loc.locate_record (request):
                    locator = loc
                    break

            # Find the base class to search for a responder.  Things that
            # match on a query string are expected to use q= for normal page
            # content or d= for other data.
            if request.query.has_key ('q'):
                responderbase = ContentResponder
            elif request.query.has_key ('d'):
                responderbase = DataResponder
            else:
                responderbase = PageResponder

            # Usually, the RecordLocator and PageResponder will be the same
            # class.  So for normal page requests, we give locator the first
            # crack at responding.
            response = None
            if responderbase is PageResponder and locator is not None and issubclass (locator, PageResponder):
                try:
                    response = locator.respond (request)
                except:
                    if request.http:
                        response = None
                    else:
                        raise

            # If locator didn't pan out, give other responders a shot.
            if response is None:
                for responder in responderbase.get_extensions ():
                    try:
                        response = responder.respond (request)
                    except:
                        if request.http:
                            response = None
                        else:
                            raise
                    if response is not None:
                        break

            # Finally, if we didn't get any response, raise an exception.
            if response is None:
                raise blip.utils.BlipException ('No responder found')
        except Exception, err:
            if not request.http:
                raise
            if request.query.has_key ('q') or request.query.has_key ('d'):
                page = blip.html.AdmonBox (
                    blip.html.AdmonBox.error,
                    blip.utils.gettext (
                        'Blip does not know how to construct this content.'))
            else:
                page = blip.html.PageError (blip.utils.gettext (
                        'Blip does not know how to construct this page.  This is' +
                        ' probably because some naughty little monkeys didn\'t finish' +
                        ' their programming assignment.'))
            response = WebResponse (request)
            response.payload = page

        return response

################################################################################
## Extension Points

class RecordLocator (blinq.ext.ExtensionPoint):
    @classmethod
    def locate_record (cls, request):
        return False

class AccountHandler (blinq.reqs.Responder):
    account_handler = None

    @classmethod
    def locate_account (cls, request):
        return False
        
class PageResponder (blinq.reqs.Responder):
    pass

class ContentResponder (blinq.reqs.Responder):
    pass

class DataResponder (blinq.reqs.Responder):
    pass
