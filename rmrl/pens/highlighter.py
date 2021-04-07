# Copyright (C) 2020  Davis Remmel
# Copyright 2021 Robert Schroll
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

from .generic import GenericPen
from reportlab.graphics.shapes import Rect
from reportlab.pdfgen.pathobject import PDFPathObject
from ..annotation import Annotation, Point, Rect, QuadPoints

class HighlighterPen(GenericPen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.layer = kwargs.get('layer')
        self.annotate = True#False #TODO bool(int(QSettings().value(
        #    'pane/notebooks/export_pdf_annotate')))

    def paint_stroke(self, canvas, stroke):
        canvas.saveState()
        canvas.setLineCap(2)  # Square
        canvas.setLineJoin(1)  # Round
        #canvas.setDash ?? for solid line
        yellow = (1.000, 0.914, 0.290)
        canvas.setStrokeColor(yellow, alpha=0.392)
        canvas.setLineWidth(stroke.width)

        path = canvas.beginPath()
        path.moveTo(stroke.segments[0].x, stroke.segments[0].y)

        x0 = stroke.segments[0].x
        y0 = stroke.segments[0].y

        ll = Point(x0, y0)
        ur = Point(x0, y0)

        for segment in stroke.segments[1:]:
            path.lineTo(segment.x, segment.y)

            # Do some basic vector math to rotate the line width
            # perpendicular to this segment

            x1 = segment.x
            y1 = segment.y
            width = segment.width

            l = [x1-x0, y1-y0]
            if l[0] == 0:
                orthogonal = [1, 0]
            else:
                v0 = -l[1]/l[0] 
                scale = (1+v0**2)**0.5
                orthogonal = [v0/scale, 1/scale]

            xmin = x0-width/2*orthogonal[0]
            ymin = y0-width/2*orthogonal[1]
            xmax = x1+width/2*orthogonal[0]
            ymax = y1+width/2*orthogonal[1] 

            ll = Point(min(ll.x, xmin), min(ll.y, ymin))
            ur = Point(max(ur.x, xmax), max(ur.y, ymax))

            x0 = x1
            y0 = y1 

        if self.annotate:
            self.layer.annot_paths.append(Annotation("Highlight", Rect(ll, ur)))

        canvas.drawPath(path, stroke=1, fill=0)
        canvas.restoreState()