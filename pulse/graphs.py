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

from math import pi

import cairo

class Graph:
    def __init__ (self, width=200, height=40):
        self.width = width
        self.height = height
        self.surface = cairo.ImageSurface (cairo.FORMAT_ARGB32, self.width, self.height)
        self.context = cairo.Context (self.surface)
        # FIXME: make the whole thing white first
        #self.context.set_source_rgb (1.0, 1.0, 1.0)
        #self.context.fill_preserve ()

    def draw_border (self, thickness=2, radius=6):
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

        self.context.line_to (self.width - offset, self.height - offset - radius)
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
        self.surface.write_to_png (filename)

class BarGraph (Graph):
    def __init__ (self, stats, width=200, height=40):
        Graph.__init__ (self, width=width, height=height)
        self.context.set_antialias (cairo.ANTIALIAS_GRAY)
        # FIXME: do stuff
        self.draw_border (thickness=1, radius=1)

class PulseGraph (Graph):
    def __init__ (self, stats, width=200, height=40):
        Graph.__init__ (self, width=width, height=height)
        self.context.set_antialias (cairo.ANTIALIAS_GRAY)

        border_thickness = 1
        inner_width = self.width - (2 * border_thickness) - 2
        inner_height = self.height - (2 * border_thickness) - 4

        self.context.new_path ()

        cellWidth = (inner_width * 1.0) / len(stats)
        tickWidth = cellWidth / 9.0

        baseline = (3.0 / 4.0) * inner_height
        x = border_thickness + 1
        self.context.move_to (x, baseline)

        for stat in stats:
            amp = (baseline - border_thickness - 2) * stat
            x += tickWidth
            self.context.line_to (x, baseline)
            x += tickWidth
            self.context.line_to (x, baseline + (amp / 4))
            x += 2 * tickWidth
            self.context.line_to (x, baseline - amp)
            x += 2 * tickWidth
            self.context.line_to (x, baseline + (amp / 3))
            x += tickWidth
            self.context.line_to (x, baseline)
            x += 2 * tickWidth
            self.context.line_to (x, baseline)

        self.context.set_line_cap (cairo.LINE_CAP_ROUND)
        self.context.set_line_join (cairo.LINE_JOIN_ROUND)

        self.context.set_line_width (2)
        self.context.set_source_rgb (0.6, 0.6, 0.6)
        self.context.stroke_preserve ()

        self.context.set_line_width (1)
        self.context.set_source_rgb (0.6, 0.4, 0.4)
        self.context.stroke ()

        self.draw_border (thickness=border_thickness, radius=4)
