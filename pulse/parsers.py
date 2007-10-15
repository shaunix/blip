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

