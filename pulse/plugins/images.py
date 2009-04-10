# Copyright (c) 2006-2009  Shaun McCance  <shaunm@gnome.org>
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

"""
ModuleScanner plugin for images.
"""

import Image
import os
import re
import shutil

from pulse import config

import pulse.pulsate.modules

class ImagesHandler (object):
    """
    ModuleScanner plugin for images.
    """

    def __init__ (self, scanner):
        self.scanner = scanner
        self.images = []

    def process_file (self, dirname, basename, **kw):
        """
        Process an image file in a module.
        """
        if basename.endswith ('.png'):
            self.images.append (os.path.join (dirname, basename))

    def locate_icon (self, record, icon):
        icondir = os.path.join (config.web_icons_dir, 'apps')

        if icon.endswith ('.png'):
            iconfile = icon
            icon = icon[:-4]
        else:
            iconfile = icon + '.png'
        candidates = []
        for img in self.images:
            base = os.path.basename (img)
            if os.path.basename (img) == iconfile:
                candidates.append (img)
            elif base.startswith (icon) and base.endswith ('.png'):
                mid = base[len(icon):-4]
                if re.match ('[\.-]\d\d$', mid):
                    candidates.append (img)
            elif base.startswith ('hicolor_apps_') and base.endswith (iconfile):
                candidates.append (img)
        use = None
        img22 = None
        img24 = None
        imgbig = None
        dimbig = None
        for img in candidates:
            im = Image.open (img)
            width, height = im.size
            if width == height == 24:
                img24 = img
                break
            elif width == height == 22:
                img22 = img
            elif width == height and width > 24:
                if dimbig == None or width < dimbig:
                    imgbig = img
                    dimbig = width
        use = img24 or img22
        if use != None:
            if not os.path.isdir (icondir):
                os.makedirs (icondir)
            shutil.copyfile (use, os.path.join (icondir, os.path.basename (use)))
            record.update ({'icon_dir' : 'apps', 'icon_name' : os.path.basename (use[:-4])})
        elif imgbig != None:
            if not os.path.isdir (icondir):
                os.makedirs (icondir)
            im = Image.open (imgbig)
            im.thumbnail((24, 24), Image.ANTIALIAS)
            im.save (os.path.join (icondir, os.path.basename (imgbig)), 'PNG')
            record.update ({'icon_dir' : 'apps', 'icon_name' : os.path.basename (imgbig[:-4])})
        elif record.icon_name == None or record.icon_name != icon:
            record.update (icon_dir='__icon__:apps', icon_name=icon)

pulse.pulsate.modules.ModuleScanner.register_plugin (ImagesHandler)
