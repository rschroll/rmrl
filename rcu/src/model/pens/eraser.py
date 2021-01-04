'''
eraser.py
This is the model for an Eraser QPen.

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
from PySide2.QtGui import QPainter
from .generic import GenericPen

class EraserPen(GenericPen):
    def __init__(self, color, *args, **kwargs):
        super().__init__(Qt.transparent, *args, **kwargs)

    def setColor(self, color):
        # do nothing, keep transparent
        super().setColor(Qt.transparent)

    def paint_stroke(self, painter, stroke):
        for i, segment in enumerate(stroke.segments):
            if i+1 >= len(stroke.segments):
                # no next segment, last 'to' point
                continue

            nextsegment = stroke.segments[i+1]

            # Set the width
            self.setWidthF(segment.width)

            oldcomp = painter.compositionMode()
            painter.setCompositionMode(QPainter.CompositionMode_Source)
            painter.setPen(self)
            painter.drawLine(QLineF(segment.x, segment.y,
                                    nextsegment.x, nextsegment.y))
            painter.setCompositionMode(oldcomp)
