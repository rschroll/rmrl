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

class HighlighterPen(GenericPen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layer = kwargs.get('layer')
        self.annotate = False #TODO bool(int(QSettings().value(
        #    'pane/notebooks/export_pdf_annotate')))

    def paint_stroke(self, canvas, stroke):
        canvas.saveState()
        canvas.setLineCap(2)  # Square
        canvas.setLineJoin(1)  # Round
        #canvas.setDash ?? for solid line
        canvas.setStrokeColor((1.000, 0.914, 0.290), alpha=0.392)
        canvas.setLineWidth(stroke.width)

        path = canvas.beginPath()
        path.moveTo(stroke.segments[0].x, stroke.segments[0].y)
        for segment in stroke.segments[1:]:
            path.lineTo(segment.x, segment.y)
        canvas.drawPath(path, stroke=1, fill=0)
        canvas.restoreState()

        if self.annotate:
            assert False
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
