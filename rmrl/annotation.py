# Copyright 2021 Ben Rush 
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

from __future__ import annotations

class Point:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
    
    def toList(self) -> list:
        return [self.x, self.y]

class Rect:
    """
    From PDF spec:
    a specific array object used to describe locations on a page and 
    bounding boxes for a variety of objects and written as an array 
    of four numbers giving the coordinates of a pair of diagonally
    opposite corners, typically in the form [ll.x, ll.y, ur.x, ur.x]
    """

    def __init__(self, ll: Point, ur: Point):
        self.ll = ll
        self.ur = ur

    def intersects(self, rectB: Rect) -> bool:
        # To check if either rectangle is actually a line
        # For example  :  l1 ={-1,0}  r1={1,1}  l2={0,-1}  r2={0,1}
        
        if (self.ll.x == self.ur.x or self.ll.y == self.ur.y or rectB.ll.x == rectB.ur.x or rectB.ll.y == rectB.ur.y):
            # the line cannot have positive overlap
            return False
        
        
        # If one rectangle is on left side of other
        if(self.ll.x >= rectB.ur.y or rectB.ll.x >= self.ur.y):
            return False

        # If one rectangle is above other
        if(self.ur.y <= rectB.ll.y or rectB.ur.y <= self.ll.y):
            return False

        return True

    def union(self, rectB: Rect) -> Rect:
        ll = Point(min(self.ll.x, rectB.ll.x),
                    min(self.ll.y, rectB.ll.y))
        ur = Point(max(self.ur.x, rectB.ur.x),
                    max(self.ur.y, rectB.ur.y))
        return Rect(ll, ur)

    def toList(self) -> list:
        return [self.ll.x, self.ll.y, self.ur.x, self.ur.y]
        
class QuadPoints:
    """
    From PDF spec:
    An array of 8 x n numbers specifying the coordinates of n quadrilaterals
    in default user space. Each quadrilateral shall encompass a word or group
    of contiguous words in the text underlying the annotation. The coordinates
    for each quadrilateral shall be given in the order x1, y1, x2, y2, x3, y3, x4, y4
    specifying the quadrilateral's four vertices in counterclockwise order 
    starting with the lower left. The text shall be oriented with respect to the 
    edge connecting points (x1, y1) with (x2, y2).
    """

    points: list[Point]

    def __init__(self, points: list[Point]):
        self.points = points

    def append(self, quadpoints: QuadPoints) -> QuadPoints:
        return QuadPoints(self.points + quadpoints.points)

    def toList(self) -> list:
        return [c for p in points for c in p.toList()]

    
    @staticmethod
    def fromRect(rect: Rect):
        """
        Assumes that the rect is aligned with the text. Will return incorrect
        results otherwise
        """
        # Needs to be in this order to account for rotations applied later?
        # ll.x, ur.y, ur.x, ur.y, ll.x, ll.y, ur.x, ll.y
        quadpoints = [Point(rect.ll.x, rect.ur.y),
                      Point(rect.ur.x, rect.ur.y),
                      Point(rect.ll.x, rect.ll.y),
                      Point(rect.ur.x, rect.ll.y)]
        return QuadPoints(quadpoints)

class Annotation():
    annotype: str
    rect: Rect
    quadpoints: QuadPoints

    def __init__(self, annotype: str, rect: Rect, quadpoints: list = None):
        self.annotype = annotype
        self.rect = rect
        if quadpoints:
            self.quadpoints = quadpoints
        else:
            self.quadpoints = QuadPoints.fromRect(rect)

    def united(self, annot: Annotation) -> Annotation:
        if self.annotype != annot.annotype:
            raise Exception("Cannot merge annotations with different types")
        
        return Annotation(self.annotype, 
                            self.rect.union(annot.rect), 
                            self.quadpoints.append(annot.quadpoints))

    def intersects(self, annot: Annotation) -> bool:
        return self.rect.intersects(annot.rect)
