'''
erasearea.py
This is the model for an Erase Area QPen.

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

from PySide2.QtCore import Qt
from PySide2.QtGui import QPen

class EraseAreaPen(QPen):
    def __init__(self, *args, **kwargs):
        super(type(self), self).__init__(*args, **kwargs)
        self.setCapStyle(Qt.RoundCap)
        self.setJoinStyle(Qt.MiterJoin)
        self.setStyle(Qt.SolidLine)
    
    def paint_stroke(self, painter, stroke):
        # Don't paint anything.
        return
