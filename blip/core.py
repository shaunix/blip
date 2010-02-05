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

import os
import os.path

def import_plugins (domain):
    import blip.plugins
    plugdir = os.path.dirname (blip.plugins.__file__)
    for pkg in os.listdir (plugdir):
        if os.path.isdir (os.path.join (plugdir, pkg)):
            try:
                __import__ ('blip.plugins.' + pkg + '.' + domain)
            except ImportError:
                pass

class ExtensionPoint (object):
    @classmethod
    def get_extensions (cls):
        extensions = []
        for subcls in cls.__subclasses__():
            extensions = extensions + [subcls] + subcls.get_extensions()
        return extensions


class Request (object):
    pass


class Response (object):
    def __init__ (self):
        self._return_code = 0

    def get_return_code (self):
        return self._return_code

    def set_return_code (self, code):
        self._return_code = code


class Responder (ExtensionPoint):
    @classmethod
    def respond (cls, request, **kw):
        raise NotImplementedError ('%s does not provide the respond method.'
                                   % cls.__name__)

