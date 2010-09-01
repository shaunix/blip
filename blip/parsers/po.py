# Copyright (c) 2007-2010  Shaun McCance  <shaunm@gnome.org>
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

import re

import blip.utils

class Po (object):
    """
    Parse a PO file.

    You can pass a file descriptor, a filename, or None to the constructor.
    If a file descriptor of filename is passed, it will automatically parse
    the file.  Otherwise, you must manually pass data to the feed method
    and call the finish method when you're done.
    """

    def __init__ (self, fd=None):
        if isinstance (fd, basestring):
            self._fd = codecs.open (fd, 'r', 'utf-8')
        elif isinstance (fd, file):
            self._fd = fd
        else:
            self._fd = None
        self._msgstrs = blip.utils.odict()
        self._images = {}
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
        if self._fd is not None:
            for line in self._fd:
                self.feed (line)
            self.finish ()

    def feed (self, line):
        """Pass a line of data to the parser."""
        line = line.strip()
        if line.startswith ('#~'):
            return

        if line.startswith ('msgid "'):
            if self._inkey.startswith ('msg'):
                self.finish ()
            self._inkey = 'msgid'
            line = line[6:]
        elif line.startswith ('msgid_plural'):
            self._inkey = 'msgid_plural'
            line = line[13:]
        elif line.startswith ('msgctxt "'):
            self._inkey = 'msgctxt'
            line = line[8:]
        elif line.startswith ('msgstr "'):
            self._inkey = 'msgstr'
            line = line[7:]
        elif line.startswith ('msgstr['):
            br = line.find (']')
            self._inkey = line[:br + 1]
            line = line[br + 2:]
        elif line.startswith ('#'):
            if self._inkey.startswith ('msg'):
                self.finish ()
            self._inkey = 'comment'
        elif line == '':
            self.finish ()

        if self._inkey.startswith ('msg'):
            if line.startswith ('"') and line.endswith ('"'):
                self._msg.setdefault (self._inkey, '')
                # FIXME: unescape \"
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
        """Finish parsing manually fed data."""
        if self._msg.has_key ('msgid'):
            key = (self._msg['msgid'], self._msg.get ('msgid_plural'), self._msg.get('msgctxt'))
            self._comments[key] = self._msg.get('comment')
            if self._msg.has_key ('msgstr'):
                self._msgstrs[key] = [self._msg['msgstr']]
            else:
                self._msgstrs[key] = []
                i = 0
                while True:
                    msgi = 'msgstr[' + str(i) + ']'
                    if self._msg.has_key (msgi):
                        self._msgstrs[key].append (self._msg[msgi])
                        i += 1
                    else:
                        break
            # Get stats for xml2po's @@image messages
            img = self._msg['msgid'].startswith ('@@image: ')
            imgname = None
            if img:
                self._num_images += 1
                imgname = re.match('@@image: \'([^\']*)\';', self._msg['msgid'])
                if imgname:
                    imgname = imgname.group(1)
                else:
                    imgname = None
            # Safe to use msgstr, because these are never pluralized
            if self._msg.get('msgstr', '') == '':
                self._num_untranslated += 1
                if img:
                    self._num_untranslated_images += 1
                    if imgname:
                        self._images[imgname] = 'untranslated'
            elif self._msg.get('fuzzy', False):
                self._num_fuzzy += 1
                if img:
                    self._num_fuzzy_images += 1
                    if imgname:
                        self._images[imgname] = 'fuzzy'
            else:
                self._num_translated += 1
                if img:
                    self._num_translated_images += 1
                    if imgname:
                        self._images[imgname] = 'translated'
        self._inkey = ''
        self._msg = {}

    def get_messages (self):
        """Get a list of all messages."""
        return self._msgstrs.keys()

    def has_message (self, msgkey):
        """Check if the PO file has a given message."""
        if isinstance (msgkey, basestring):
            msgkey = (msgkey, None, None)
        return self._msgstrs.has_key (msgkey)

    def get_translations (self, msgkey):
        """Get the translated message string for a given message."""
        if isinstance (msgkey, basestring):
            msgkey = (msgkey, None, None)
        return self._msgstrs[msgkey]
        
    def get_comment (self, msgkey):
        """Get the translator comment for a given message."""
        if isinstance (msgkey, basestring):
            msgkey = (msgkey, None, None)
        return self._comments[msgkey]

    def get_num_messages (self):
        """Get the total number of messages in this PO file."""
        return len(self._msgstrs)

    def get_stats (self):
        """Get the number of translated, fuzzy, and untranslated messages as a tuple."""
        return (self._num_translated, self._num_fuzzy, self._num_untranslated)

    def get_image_stats (self):
        """Get the statistics for documentation image message only."""
        return (self._num_translated_images, self._num_fuzzy_images, self._num_untranslated_images)

    def get_image_status (self, img):
        """Get the status of an image."""
        return self._images.get(img)
