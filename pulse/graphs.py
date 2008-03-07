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

"""
Generate various types of graphs
"""

from math import pi

import colorsys
import os
import os.path

import cairo

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
        self.surface.write_to_png (filename)


class BarGraph (Graph):
    """
    Simple bar graph

    BarGraph takes a list of statistics and a maximum value and constructs
    a bar graph, where the height of each bar is determined by the ratio
    of the corresponding value to the maximum value.  For values greater
    than the maximum, the bar is darkened by an amount proportional to
    the ratio.
    """

    def __init__ (self, stats, top, width=None, height=40):
        if width == None:
            width = 6 * len(stats) + 2
        Graph.__init__ (self, width=width, height=height)
        self._stats = stats
        self.context.set_antialias (cairo.ANTIALIAS_GRAY)
        alum_rgb = [0.729412, 0.741176, 0.713725]
        alum_hsv = colorsys.rgb_to_hsv (*alum_rgb)
        for i in range(len(stats)):
            stat = stats[i] / (top * 1.0) 
            self.context.new_path ()
            self.context.set_line_width (2)
            self.context.move_to (6*i + 2.5, self.height)
            self.context.rel_line_to (0, -0.5 - (self.height * min(stat, 1)))
            self.context.close_path ()
            if stat > 1:
                value = alum_hsv[2] / stat
                self.context.set_source_rgb (
                    *colorsys.hsv_to_rgb (alum_hsv[0], alum_hsv[1], value))
            else:
                self.context.set_source_rgb (*alum_rgb)
            self.context.stroke ()

    def get_coords (self):
        """
        Get the coordinates for each bar

        Returns a list of coordinates for each bar in the graph, corresponding
        to each statistic passed in.  Each coordinate is a tuple of the form
        (left, top, right, bottom), where pixel coordinates run left-to-right
        and top-to-bottom.  This is the form expected for image maps in HTML.
        """

        return [(6*i, 0, 6*i + 5, self.height) for i in range(len(self._stats))]
