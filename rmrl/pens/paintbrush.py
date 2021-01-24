'''
Copyright (C) 2020  Davis Remmel
Copyright 2021 Robert Schroll

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
'''

import math

from .generic import GenericPen
from .textures import PENCIL_TEXTURES

def point_distance(x1, y1, x2, y2):
    dist = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
    return dist

class PaintbrushPen(GenericPen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vector = kwargs.get('vector', False)

    def set_segment_properties(self, canvas, segment, nextsegment):
        # Set the width
        modwidth = segment.width * 0.75
        maxdelta = modwidth * 0.75
        delta = (segment.pressure - 1) * maxdelta
        newwidth = modwidth + delta
        canvas.setLineWidth(newwidth)

        # # We want textures only in a mid-range, with the high and
        # # low ends going to solid patterns (clamping).
        # press_mod = segment.pressure + 0.4
        # if segment.pressure < 0.25:
        #     press_mod = 0
        # elif segment.pressure > 0.7:
        #     press_mod = 1

        press_mod = segment.pressure

        # There is also some effect of speed...really fast movements
        # produce really light strokes.
        press_mod *= 2 - (segment.speed / 75)

        if self.vector:
            stroke_color = [1 - (1 - c) * press_mod / 2 for c in self.color]
            canvas.setStrokeColor(stroke_color)
        else:
            assert False
            angle = math.degrees(nextsegment.direction) + 90
            transform = QTransform().rotate(angle)

            texture = PENCIL_TEXTURES.get_log_paintbrush(press_mod)
            brush.setTextureImage(texture)
            brush.setTransform(transform)
            self.setBrush(brush)

        # If the segment is short, use a round cap.
        distance = point_distance(segment.x, segment.y,
                                    nextsegment.x, nextsegment.y)
        if distance < newwidth / 1:
            canvas.setLineCap(1)  # Rounded
        else:
            canvas.setLineCap(0)  # Flat
