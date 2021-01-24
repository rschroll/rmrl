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

from .generic import GenericPen

class MarkerPen(GenericPen):
    def set_segment_properties(self, canvas, segment, nextsegment):
        # Set the width
        # maxdelta = segment.width / 0.5
        # delta = (segment.pressure - 1) * maxdelta
        # self.setWidthF(segment.width + delta)
        canvas.setLineWidth(segment.width * 0.7)
