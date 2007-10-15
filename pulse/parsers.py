# Copyright (c) 2007  Shaun McCance  <shaunm@gnome.org>
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

import ConfigParser
import re

class Automake (object):
    def __init__ (self, filename):
        self._variables = {}
        self._lines = []
        regexp = re.compile ('''([A-Za-z_]+)(\s*=)(.*)''')
        fd = open (filename)
        line = fd.readline ()
        while line:
            if '#' in line: line = line[line.index('#')]
            match = regexp.match (line)
            if match:
                varname = match.group(1)
                vartxt = match.group(3).strip()
                if vartxt.endswith ('\\'):
                    vartxt = vartxt[:-1]
                    line = fd.readline ()
                    while line:
                        if '#' in line: line = line[line.index('#')]
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

class KeyFile (object):
    def __init__ (self, f):
        if isinstance (f, basestring):
            fd = open (f)
        else:
            fd = f
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

class Po:
    def __init__ (self, filename):
        self._filename = filename
        self._msgstrs = {}
        self._comments = {}
        self.parse()

    def parse (self):
        self._inkey = ''
        self._msg = {}

        def finish_msg ():
            if self._msg.has_key ('msgid'):
                key = (self._msg['msgid'], self._msg.get('msgctxt'))
                self._comments[key] = self._msg.get('comment')
                self._msgstrs[key] = self._msg.get('msgstr')
            self._inkey = ''
            self._msg = {}
                
        for line in open (self._filename):
            line = line.strip()
            if line.startswith ('#~'):
                continue

            if line.startswith ('msgid "'):
                if self._inkey.startswith ('msg'):
                    finish_msg ()
                self._inkey = 'msgid'
                line = line[6:]
            elif line.startswith ('msgctxt "'):
                self._inkey = 'msgctxt'
                line = line[8:]
            elif line.startswith ('msgstr "'):
                self._inkey = 'msgstr'
                line = line[7:]
            elif line.startswith ('#'):
                if self._inkey.startswith ('msg'):
                    finish_msg ()
                self._inkey = 'comment'
            elif line == '':
                finish_msg ()

            if self._inkey.startswith ('msg'):
                if line.startswith ('"') and line.endswith ('"'):
                    self._msg.setdefault (self._inkey, '')
                    self._msg[self._inkey] += line[1:-1]
            elif self._inkey == 'comment':
                self._msg.setdefault (self._inkey, '')
                if ' ' in line:
                    self._msg[self._inkey] += line[line.index(' ')+1:] + '\n'
                else:
                    self._msg[self._inkey] += '\n'

        finish_msg ()

    def has_message (self, msgid, msgctxt=None):
        return self._msgstrs.has_key ((msgid, msgctxt))

    def get_message_str (self, msgid, msgctxt=None):
        return self._msgstrs[(msgid, msgctxt)]
        
    def get_message_comment (self, msgid, msgctxt=None):
        return self._comments[(msgid, msgctxt)]

