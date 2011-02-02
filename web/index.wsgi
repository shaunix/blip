#!/usr/bin/env python
# Copyright (c) 2006-2010  Shaun McCance  <shaunm@gnome.org>
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

BLIP_PYTHON_DIR = '/usr/lib/python2.7/site-packages'

import cStringIO
import sys

if not BLIP_PYTHON_DIR in sys.path:
    sys.path.append (BLIP_PYTHON_DIR)

import blip.config
blip.config.init('@BLIP_SITE@')

import blip.db
import blip.web
import blip.utils

blip.db.block_implicit_flushes ()
blip.utils.set_log_level (None)

def application (environ, start_response):
    request = blip.web.WebRequest (environ=environ, stdin=environ['wsgi.input'])
    response = blip.web.WebResponder.respond (request)
    start_response (*response.get_response())
    blip.db.rollback ()
    fp = cStringIO.StringIO ()
    response.output_payload (fp=fp)
    yield fp.getvalue ()
    fp.close ()
