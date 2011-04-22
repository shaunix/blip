# Copyright (c) 2006-2011  Shaun McCance  <shaunm@gnome.org>
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

import codecs
import email.header
import re

import blip.utils

def score_encode (s):
    out = ''
    pat = re.compile('[A-Za-z0-9-]')
    for c in s:
        if pat.match(c):
            out += c
        else:
            out += '_' + str(ord(c))
    return out

def score_decode (s):
    out = ''
    i = 0
    while i < len(s):
        if s[i] == '_' and i + 2 < len(s):
            out += chr(int(s[i+1:i+3]))
            i += 3
        else:
            out += s[i]
            i += 1
    return out

def decode_header (s):
    strs = email.header.decode_header (s)
    for i in range(len(strs)):
        if strs[i][1] is None:
            strs[i] = blip.utils.utf8dec (strs[i][0])
        else:
            try:
                strs[i] = codecs.getdecoder(strs[i][1])(strs[i][0], 'replace')[0]
            except:
                strs[i] = blip.utils.utf8dec(strs[i][0])
    return u''.join (strs)
