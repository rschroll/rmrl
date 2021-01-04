'''
highlighter.py
This is the model for a Highlighter QPen.

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

from PySide2.QtCore import Qt, QSettings
from PySide2.QtGui import QPen, QColor, QPainterPath, QPainter, \
    QPainterPathStroker

class HighlighterPen(QPen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.layer = kwargs.get('layer')
        self.annotate = False #TODO bool(int(QSettings().value(
        #    'pane/notebooks/export_pdf_annotate')))

        self.setCapStyle(Qt.FlatCap)
        self.setJoinStyle(Qt.BevelJoin)
        self.setStyle(Qt.SolidLine)

        # Pull the color from the settings
        color = QColor(255, 233, 74, 100) #QSettings().value('pane/notebooks/export_pdf_highlightink')
        super().setColor(color)

    def setColor(self, color):
        # Highlighter color is not adjustable like the others (using
        # the color index)
        return

    def paint_stroke(self, painter, stroke):
        path = QPainterPath()
        path.moveTo(stroke.segments[0].x, stroke.segments[0].y)

        for i, segment in enumerate(stroke.segments, 1):
            path.lineTo(segment.x, segment.y)

        self.setWidthF(stroke.width)
        painter.setPen(self)
        old_comp = painter.compositionMode()
        painter.setCompositionMode(QPainter.CompositionMode_Overlay)
        painter.drawPath(path)
        painter.setCompositionMode(old_comp)

        if self.annotate:
            # Create outline of the path. Annotations that are close to
            # each other get groups. This is determined by overlapping
            # paths. In order to fuzz this, we'll double the normal
            # width and extend the end caps.
            self.setWidthF(self.widthF() * 2)
            self.setCapStyle(Qt.SquareCap)
            opath = QPainterPathStroker(self).createStroke(path)
            # The annotation type is carried all the way through. This
            # is the type specified in the PDF spec.
            self.layer.annot_paths.append(('Highlight', opath))
