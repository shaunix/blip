# Copyright (c) 2006, 2010  Shaun McCance  <shaunm@gnome.org>
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

"""
Generate various types of graphs
"""

from math import pi

import colorsys
import os
import os.path

import cairo

import blip.utils

class Graph:
    """
    Base class for all graphs
    """

    def __init__ (self, width=200, height=40):
        self.width = width
        self.height = height
        self.surface = cairo.ImageSurface (cairo.FORMAT_ARGB32,
                                           self.width, self.height)
        self.context = cairo.Context (self.surface)

    def draw_border (self, thickness=2, radius=6):
        """
        Draw a border around a graph

        This function may be called by graph implementations to draw a border
        around the drawing context.  The thickness and radius for rounded
        corners can be controlled with the thickness and radius arguments.
        """

        self.context.new_path ()
        self.context.set_line_width (thickness)
        offset = thickness + 1
        self.context.move_to (offset, offset + radius)
        self.context.arc (offset + radius,
                          offset + radius,
                          radius, pi, 3 * pi / 2)

        self.context.line_to (self.width - offset - radius, offset)
        self.context.arc (self.width - offset - radius,
                          offset + radius,
                          radius, 3 * pi / 2, 2 * pi)

        self.context.line_to (self.width - offset,
                              self.height - offset - radius)
        self.context.arc (self.width - offset - radius,
                          self.height - offset - radius,
                          radius, 2 * pi, pi / 2)

        self.context.line_to (offset + radius, self.height - offset)
        self.context.arc (offset + radius,
                          self.height - offset - radius,
                          radius, pi / 2, pi)

        self.context.close_path ()
        self.context.set_source_rgb (0.180392, 0.203922, 0.211765)
        self.context.stroke ()

    def save (self, filename):
        """
        Save the graph to a PNG file
        """

        filedir = os.path.dirname (filename)
        if not os.path.exists (filedir):
            os.makedirs (filedir)
        # Cairo tries to decode the filename from UTF-8, even though
        # filename is already a unicode object. This causes a segfault.
        # Re-encode so Cairo can decode.
        self.surface.write_to_png (blip.utils.utf8enc (filename))


class BarGraph (Graph):
    """
    Simple bar graph

    BarGraph takes a list of statistics and a maximum value and constructs
    a bar graph, where the height of each bar is determined by the ratio
    of the corresponding value to the maximum value.  For values greater
    than the maximum, the bar is darkened by an amount proportional to
    the ratio.
    """

    def __init__ (self, stats, top, **kw):
        self._stats = stats
        self._tight = kw.get ('tight', False)
        if self._tight:
            width = kw.get ('width', len(stats))
            line_width = 1
            def get_left (i):
                return i
        else:
            width = kw.get ('width', 5 * len(stats))
            line_width = 4
            def get_left (i):
                return 5 * i
        height = kw.get ('height', 40)
        Graph.__init__ (self, width=width, height=height)
        self.context.set_antialias (cairo.ANTIALIAS_GRAY)
        alum_rgb = [0.729412, 0.741176, 0.713725]
        alum_hsv = colorsys.rgb_to_hsv (*alum_rgb)
        for i in range(len(stats)):
            stat = stats[i] / (top * 1.0) 
            self.context.new_path ()
            self.context.set_line_width (line_width)
            barleft = get_left (i)
            bartop = self.height - (self.height * min(stat, 1))
            self.context.move_to (barleft, self.height)
            self.context.line_to (barleft, bartop)
            self.context.line_to (barleft + line_width, bartop)
            self.context.line_to (barleft + line_width, self.height)
            self.context.close_path ()
            if stat > 1:
                value = alum_hsv[2] / stat
                self.context.set_source_rgb (
                    *colorsys.hsv_to_rgb (alum_hsv[0], alum_hsv[1], value))
            else:
                self.context.set_source_rgb (*alum_rgb)
            self.context.fill ()

    def get_coords (self):
        """
        Get the coordinates for each bar

        Returns a list of coordinates for each bar in the graph, corresponding
        to each statistic passed in.  Each coordinate is a tuple of the form
        (left, top, right, bottom), where pixel coordinates run left-to-right
        and top-to-bottom.  This is the form expected for image maps in HTML.
        """
        # FIXME: this is wrong for tight=True, but we're not using coords
        # for tight graphs, so it doesn't matter much.
        return [(5*i, 0, 5*i + 4, self.height) for i in range(len(self._stats))]


class LineGraph (Graph):
    def __init__ (self, stats, **kw):
        top = max (stats)
        spacing = kw.get('spacing', 5)
        width = spacing * (len(stats) - 1)
        height = kw.get ('height', 40)
        Graph.__init__ (self, width=width, height=height)
        self.context.set_antialias (cairo.ANTIALIAS_GRAY)
        fill_rgb = [0.447059, 0.623529, 0.811765]
        line_rgb = [0.203922, 0.396078, 0.643137]
        self.context.new_path ()
        height -= 2
        last = -1
        for i in range(len(stats)):
            if stats[i] != None:
                stat = stats[i] / (top * 1.0)
                if last >= 0:
                    self.context.line_to (i * spacing, height - (height * stat) + 1.5)
                else:
                    self.context.move_to (0, height - (height * stat) + 1.5)
                    if i != 0:
                        self.context.line_to (i * spacing, height - (height * stat) + 1.5)
                last = i
        if last != len(stats) - 1:
            self.context.rel_line_to (width - (last * spacing), 0)
        self.context.set_line_width (2)
        self.context.set_source_rgb (*line_rgb)
        self.context.stroke_preserve ()
        self.context.line_to (width, height)
        self.context.line_to (0, height)
        self.context.set_source_rgb (*fill_rgb)
        self.context.fill ()
