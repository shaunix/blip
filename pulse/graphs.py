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

def drawPulse (file, stats, width=200, height=40):
    surface = cairo.ImageSurface (cairo.FORMAT_ARGB32,
                                  width, height)
    ctx = cairo.Context (surface)
    ctx.set_antialias (cairo.ANTIALIAS_GRAY)

    border = 2
    _drawBorder (ctx, width=width, height=height,
                 lineWidth=2, radius=6)

    width_ = width - (border * 2)
    height_ = height - (border * 2)
    
    ctx.new_path ()

    cellWidth = (width_ * 1.0) / len(stats)
    tickWidth = cellWidth / 9.0

    y = (height_ * 3.0) / 4.0
    x = border
    ctx.move_to (x, y)

    for stat in stats:
        amp = y * stat
        x += tickWidth
        ctx.line_to (x, y)
        x += tickWidth
        ctx.line_to (x, y + (amp / 4))
        x += 2 * tickWidth
        ctx.line_to (x, y - amp)
        x += 2 * tickWidth
        ctx.line_to (x, y + (amp / 3))
        x += tickWidth
        ctx.line_to (x, y)
        x += 2 * tickWidth
        ctx.line_to (x, y)

    ctx.set_line_cap (cairo.LINE_CAP_ROUND)
    ctx.set_line_join (cairo.LINE_JOIN_ROUND)

    ctx.set_line_width (2)
    ctx.set_source_rgb (0.6, 0.6, 0.6)
    ctx.stroke_preserve ()

    ctx.set_line_width (1)
    ctx.set_source_rgb (0.6, 0.4, 0.4)
    ctx.stroke ()

    surface.write_to_png (file)

def _drawBorder (ctx, width, height, lineWidth=2, radius=6):
    ctx.new_path ()
    ctx.set_line_width (lineWidth)
    ctx.move_to (lineWidth / 2.0, radius)
    ctx.arc (radius + 1,
             radius + 1,
             radius, pi, 3 * pi / 2)
    ctx.arc (width - radius - 1,
             radius + 1,
             radius, 3 * pi / 2, 2 * pi)
    ctx.arc (width - radius - 1,
             height - radius - 1,
             radius, 2 * pi, pi / 2)
    ctx.arc (radius + 1,
             height - radius - 1,
             radius, pi / 2, pi)
    ctx.close_path ()
    ctx.set_source_rgb (1.0, 1.0, 1.0)
    ctx.fill_preserve ()
    ctx.set_source_rgb (0.6, 0.6, 0.6)
    ctx.stroke ()
