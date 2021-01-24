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
from .textures import PENCIL_TEXTURES

class PencilPen(GenericPen):

    def set_segment_properties(self, canvas, segment, nextsegment):
        basewidth = segment.width
        deltamax = 0.42 * basewidth
        delta = -deltamax
        prim_width = basewidth + delta
        canvas.setLineWidth(prim_width)

        stroke_color = [1 - (1 - c) * segment.pressure for c in self.color]
        canvas.setStrokeColor(stroke_color)

    def old_paint_stroke(self, painter, stroke):
        assert False
        brush = QBrush()
        brush.setColor(self.color())

        # if self.vector:
        #     path = QPainterPath()
        #     path.moveTo(stroke.segments[0].x, stroke.segments[0].y)
        #     for i, segment in enumerate(stroke.segments, 1):
        #         path.lineTo(segment.x, segment.y)
        #     self.setWidthF(stroke.width)
        #     painter.setPen(self)
        #     painter.drawPath(path)
        #     return

        for i, segment in enumerate(stroke.segments):
            if i+1 >= len(stroke.segments):
                # no next segment, last 'to' point
                break

            nextsegment = stroke.segments[i+1]

            # # Direction has something to do with the brush shape...
            # print(segment.direction)

            # I experimented with a weighted pressure, but I don't think
            # the rM uses it! So, use a static pressure.
            # Experiment details: look at previous _n_ segment pressures
            # and average, where n={5,10,20,50,100,200) -- all this does
            # is blur the pressures, and all make it look further than
            # the truth.

            # # If the segment is short, use a round cap.
            # distance = point_distance(segment.x, segment.y,
            #                           nextsegment.x, nextsegment.y)
            # if distance < newwidth / 2:
            #     self.setCapStyle(Qt.RoundCap)
            # else:
            #     self.setCapStyle(Qt.FlatCap)

            # There is a spatter around the pencil. We are going to draw
            # two strokes: one for the primary, and another for the
            # spatter. The spatter is drawn first, so that it appears
            # behind in the vector versions.

            # Draw primary stroke
            basewidth = segment.width
            deltamax = 0.42 * basewidth
            delta = -deltamax
            prim_width = basewidth + delta
            self.setWidthF(prim_width)

            if self.vector:
                if not self.ocolor:
                    self.ocolor = self.color()
                ncolor = QColor()
                ncolor.setRedF(1 - ((1 - self.ocolor.redF()) * segment.pressure))
                ncolor.setGreenF(1 - ((1 - self.ocolor.greenF()) * segment.pressure))
                ncolor.setBlueF(1 - ((1 - self.ocolor.blueF()) * segment.pressure))
                self.setColor(ncolor)
            else:
                texture = PENCIL_TEXTURES.get_log(segment.pressure)
                brush.setTextureImage(texture)
                self.setBrush(brush)
            painter.setPen(self)
            painter.drawLine(QLineF(segment.x, segment.y,
                                    nextsegment.x, nextsegment.y))

            # Draw spatter stroke, but only if not vector because there
            # are compositing problems.
            if not self.vector:
                spat_width = prim_width * 1.25
                self.setWidthF(spat_width)

                texture = PENCIL_TEXTURES.get_log(segment.pressure * 0.7)
                brush.setTextureImage(texture)
                self.setBrush(brush)
                painter.setPen(self)
                painter.drawLine(QLineF(segment.x, segment.y,
                                        nextsegment.x, nextsegment.y))
