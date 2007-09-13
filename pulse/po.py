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

import codecs

class PoFile (object):
    def __init__ (self, path):
        self._msg = {}
        messages = []
        this = {'comments': u'',
                'reference': u'',
                'flags': u'',
                'msgid': u'',
                'msgstr': u''}
        add = False
        into = None
        # FIXME: they're not necessarily in utf-8
        fd = codecs.open (path, 'r', 'utf-8')
        for line in fd:
            if line.isspace():
                if add:
                    messages.append (this)
                add = False
                into = None
                this = {'comments': u'',
                        'reference': u'',
                        'flags': u'',
                        'msgid': u'',
                        'msgstr': u''}
            elif line.startswith ('#.'):
                add = True
                into = None
                this['comments'] = this['comments'] + line[2:]
            elif line.startswith ('#:'):
                add = True
                into = None
                this['reference'] = this['reference'] + line[2:]
            elif line.startswith ('#,'):
                add = True
                into = None
                this['flags'] = this['flags'] + line[2:]
            elif line.startswith ('msgid '):
                line = line[6:].strip()
                into = 'msgid'
            elif line.startswith ('msgid_plural '):
                line = line[13:].strip()
                into = 'msgid_plural'
            elif line.startswith ('msgstr '):
                line = line[7:].strip()
                into = 'msgstr'
            elif line.startswith ('msgstr['):
                line = line[7:]
                num = line[: line.index(']')]
                line = line[line.index(']') + 1 :].strip()
                into = 'msgstr' + num
            if line.startswith ('"') and into != None:
                line = line[1:].strip()
                if line.endswith ('"'):
                    line = line[:-1]
                else:
                    continue
                if line != u'':
                    add = True
                    this.setdefault (into, u'')
                    this[into] = (this[into] +
                                  line.replace('\\n', '\n').replace('\\"', '"'))
        if add:
            messages.append (this)
        fd.close()

        for msg in messages:
            self._msg[msg['msgid']] = msg

    def keys (self):
        return self._msg.keys()
    def values (self):
        return self._msg.values()
    def has_key (self, key):
        return self._msg.has_key (key)
    def __getitem__ (self, key):
        return self._msg.get (key, None)
