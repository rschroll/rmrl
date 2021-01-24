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

class MechanicalPencilPen(GenericPen):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vector = kwargs.get('vector', False)

    def set_segment_properties(self, canvas, segment, nextsegment):
        # Set the width
        canvas.setLineWidth(segment.width / 1.5)

        # Set the brush/pattern
        if self.vector:
            stroke_color = [1 - (1 - c) * segment.pressure for c in self.color]
            canvas.setStrokeColor(stroke_color)
        else:
            assert False
            brush.setColor(self.color())
            texture = PENCIL_TEXTURES.get_linear(0.00)
            pressure_textures = [
                PENCIL_TEXTURES.get_linear(0.10),
                PENCIL_TEXTURES.get_linear(0.15),
                PENCIL_TEXTURES.get_linear(0.20),
                PENCIL_TEXTURES.get_linear(0.25),
                PENCIL_TEXTURES.get_linear(0.30),
                PENCIL_TEXTURES.get_linear(0.40),
                PENCIL_TEXTURES.get_linear(0.50),
                PENCIL_TEXTURES.get_linear(0.60),
                PENCIL_TEXTURES.get_linear(0.70),
                PENCIL_TEXTURES.get_linear(0.80),
                PENCIL_TEXTURES.get_linear(0.90)
            ]
            for n, tex in enumerate(pressure_textures):
                threshold = n / len(pressure_textures)
                if segment.pressure >= threshold:
                    texture = tex
            brush.setTextureImage(texture)
            self.setBrush(brush)
