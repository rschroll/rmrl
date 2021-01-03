'''
marker.py
This is the model for a Marker QPen.

RCU is a synchronization tool for the reMarkable Tablet.
Copyright (C) 2020  Davis Remmel

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

from PySide2.QtCore import Qt, QLineF
from PySide2.QtGui import QPen

class MarkerPen(QPen):
    def __init__(self, *args, **kwargs):
        super(type(self), self).__init__(*args, **kwargs)
        self.setCapStyle(Qt.RoundCap)
        self.setJoinStyle(Qt.MiterJoin)
        self.setStyle(Qt.SolidLine)
    
    def paint_stroke(self, painter, stroke):
        for i, segment in enumerate(stroke.segments):
            if i+1 >= len(stroke.segments):
                # no next segment, last 'to' point
                continue
            
            nextsegment = stroke.segments[i+1]

            # Set the width
            # maxdelta = segment.width / 0.5
            # delta = (segment.pressure - 1) * maxdelta
            # self.setWidthF(segment.width + delta)
            self.setWidthF(segment.width * 0.7)

            painter.setPen(self)
            painter.drawLine(QLineF(segment.x, segment.y,
                                    nextsegment.x, nextsegment.y))
