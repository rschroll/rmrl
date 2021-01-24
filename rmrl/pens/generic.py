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

def pairs(iterable):
    it = iter(iterable)
    old = next(it)
    for new in it:
        yield (old, new)
        old = new

class GenericPen(object):
    def __init__(self, color, *args, **kwargs):
        self.color = color

    def paint_stroke(self, canvas, stroke):
        canvas.saveState()
        canvas.setLineCap(1)  # Rounded
        canvas.setLineJoin(1)  # Round join
        #canvas.setDash ?? for solid line
        canvas.setStrokeColor(self.color)
        for p1, p2 in pairs(stroke.segments):
            self.set_segment_properties(canvas, p1, p2)
            canvas.line(p1.x, p1.y, p2.x, p2.y)
        canvas.restoreState()

    def set_segment_properties(self, canvas, segment, nextsegment):
        # Set the width
        canvas.setLineWidth(segment.width)
