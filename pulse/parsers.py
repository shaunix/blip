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

import codecs
import ConfigParser
import re

import pulse.utils


class Automake (object):
    """
    Parse a Makefile.am file

    This class parses a Makefile.am file, allowing you to extract information
    from them.  Directives for make are ignored.  This is only useful for
    extracting variables.
    """

    def __init__ (self, filename):
        self._variables = {}
        self._lines = []
        regexp = re.compile ('''([A-Za-z_]+)(\s*=)(.*)''')
        fd = open (filename)
        line = fd.readline ()
        while line:
            if '#' in line:
                line = line[line.index('#')]
            match = regexp.match (line)
            if match:
                varname = match.group(1)
                vartxt = match.group(3).strip()
                if vartxt.endswith ('\\'):
                    vartxt = vartxt[:-1]
                    line = fd.readline ()
                    while line:
                        if '#' in line:
                            line = line[line.index('#')]
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
        """
        Get the canonicalized lines from the automake file
        """
        return self._lines

    def __getitem__ (self, key):
        """
        Get the value of an automake variable
        """
        return self._variables[key]

    def get (self, key, val=None):
        """
        Get the value of an automake variable, or return a default
        """
        return self._variables.get(key, val)

    def has_key (self, key):
        """
        Check if the variable is set in the automake file
        """
        return self._variables.has_key (key)


class KeyFile (object):
    """
    Parse a KeyFile, like those defined by the Desktop Entry Specification
    """
    
    def __init__ (self, fd):
        if isinstance (fd, basestring):
            fd = codecs.open (fd, 'r', 'utf-8')
        cfg = ConfigParser.ConfigParser()
        cfg.optionxform = str
        cfg.readfp (fd)
        self._data = {}
        for group in cfg.sections ():
            self._data[group] = {}
            for key, value in cfg.items (group):
                left = key.find ('[')
                right = key.find (']')
                if not isinstance (value, unicode):
                    value = unicode(value, 'utf-8')
                if left >= 0 and right > left:
                    keybase = key[0:left]
                    keylang = key[left+1:right]
                    self._data[group].setdefault (keybase, {})
                    if isinstance (self._data[group][keybase], basestring):
                        self._data[group][keybase] = {'C' : self._data[group][keybase]}
                    self._data[group][keybase][keylang] = value
                else:
                    if self._data[group].has_key (key):
                        if isinstance (self._data[group][key], dict):
                            self._data[group][key]['C'] = value
                        else:
                            raise pulse.utils.PulseException ('Duplicate entry for %s in %s'
                                                              % (key, fd.name))
                    else:
                        self._data[group][key] = value

    def get_groups (self):
        """
        Get the groups from the key file
        """
        return self._data.keys()

    def has_group (self, group):
        """
        Check if the key file has a group
        """
        return self._data.has_key (group)

    def get_keys (self, group):
        """
        Get the keys that are set in a group in the key file
        """
        return self._data[group].keys()

    def has_key (self, group, key):
        """
        Check if a key is set in a group in the key file
        """
        return self._data[group].has_key (key)

    def get_value (self, group, key):
        """
        Get the value of a key in a group in the key file
        """
        return self._data[group][key]


class Po:
    def __init__ (self, fd=None):
        if isinstance (fd, basestring):
            self._fd = codecs.open (fd, 'r', 'utf-8')
        elif isinstance (fd, file):
            self._fd = fd
        else:
            self._fd = None
        self._msgstrs = {}
        self._comments = {}
        self._num_translated = 0
        self._num_untranslated = 0
        self._num_fuzzy = 0
        self._num_images = 0
        self._num_translated_images = 0
        self._num_fuzzy_images = 0
        self._num_untranslated_images = 0

        self._inkey = ''
        self._msg = {}
        if self._fd != None:
            for line in self._fd:
                self.feed (line)
            self.finish ()

    def feed (self, line):
        line = line.strip()
        if line.startswith ('#~'):
            return

        if line.startswith ('msgid "'):
            if self._inkey.startswith ('msg'):
                self.finish ()
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
                self.finish ()
            self._inkey = 'comment'
        elif line == '':
            self.finish ()

        if self._inkey.startswith ('msg'):
            if line.startswith ('"') and line.endswith ('"'):
                self._msg.setdefault (self._inkey, '')
                self._msg[self._inkey] += line[1:-1]
        elif self._inkey == 'comment':
            self._msg.setdefault (self._inkey, '')
            if line == '#, fuzzy':
                self._msg['fuzzy'] = True
            if ' ' in line:
                self._msg[self._inkey] += line[line.index(' ')+1:] + '\n'
            else:
                self._msg[self._inkey] += '\n'

    def finish (self):
        if self._msg.has_key ('msgid'):
            key = (self._msg['msgid'], self._msg.get('msgctxt'))
            self._comments[key] = self._msg.get('comment')
            self._msgstrs[key] = self._msg.get('msgstr')
            img = self._msg['msgid'].startswith ('@@image: ')
            if img:
                self._num_images += 1
            if self._msg.get('msgstr', '') == '':
                self._num_untranslated += 1
                if img:
                    self._num_untranslated_images += 1
            elif self._msg.get('fuzzy', False):
                self._num_fuzzy += 1
                if img:
                    self._num_fuzzy_images += 1
            else:
                self._num_translated += 1
                if img:
                    self._num_translated_images += 1
        self._inkey = ''
        self._msg = {}

    def has_message (self, msgid, msgctxt=None):
        return self._msgstrs.has_key ((msgid, msgctxt))

    def get_message_str (self, msgid, msgctxt=None):
        return self._msgstrs[(msgid, msgctxt)]
        
    def get_message_comment (self, msgid, msgctxt=None):
        return self._comments[(msgid, msgctxt)]

    def get_num_messages (self):
        return len(self._msgstrs)

    def get_stats (self):
        return (self._num_translated, self._num_fuzzy, self._num_untranslated)

    def get_image_stats (self):
        return (self._num_translated_images, self._num_fuzzy_images, self._num_untranslated_images)
