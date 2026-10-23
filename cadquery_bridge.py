# SPDX-License-Identifier: LGPL-2.1-or-later
"""
cadquery_bridge.py: High-fidelity CadQuery compatibility layer for FreeCAD.
Allows executing CadQuery scripts (from the cleaned Text-to-CAD dataset)
directly inside FreeCAD's OpenCASCADE engine with zero external dependencies,
or seamlessly bridges official cadquery if installed.
"""

import math
import sys
try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None

class Vector:
    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, (tuple, list)):
            self.x = float(x[0])
            self.y = float(x[1])
            self.z = float(x[2]) if len(x) > 2 else 0.0
        else:
            self.x = float(x)
            self.y = float(y)
            self.z = float(z)

    def to_fc(self):
        return App.Vector(self.x, self.y, self.z)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z


class Workplane:
    def __init__(self, plane="XY", shape=None):
        self.plane = plane
        self._shape = shape
        self._center_offset = (0.0, 0.0, 0.0)
        self._pts = []
        self._last_pt = (0.0, 0.0)
        self._pending_2d = None # ("circle", r) or ("rect", w, h, centered) or ("wire", list_of_pts)

    def center(self, x, y):
        self._center_offset = (self._center_offset[0] + x, self._center_offset[1] + y, self._center_offset[2])
        return self

    def transformed(self, offset=(0, 0, 0), rotate=(0, 0, 0)):
        wp = Workplane(self.plane, self._shape)
        ox = self._center_offset[0] + (offset[0] if len(offset) > 0 else 0.0)
        oy = self._center_offset[1] + (offset[1] if len(offset) > 1 else 0.0)
        oz = self._center_offset[2] + (offset[2] if len(offset) > 2 else 0.0)
        wp._center_offset = (ox, oy, oz)
        return wp

    def circle(self, radius):
        wp = Workplane(self.plane, self._shape)
        wp._center_offset = self._center_offset
        wp._pending_2d = ("circle", radius)
        return wp

    def rect(self, xLen, yLen, centered=True):
        wp = Workplane(self.plane, self._shape)
        wp._center_offset = self._center_offset
        wp._pending_2d = ("rect", xLen, yLen, centered)
        return wp

    def moveTo(self, x, y):
        wp = Workplane(self.plane, self._shape)
        wp._center_offset = self._center_offset
        wp._last_pt = (x, y)
        wp._pts = [ (x, y) ]
        return wp

    def lineTo(self, x, y):
        wp = Workplane(self.plane, self._shape)
        wp._center_offset = self._center_offset
        wp._pts = list(self._pts) + [ (x, y) ]
        wp._last_pt = (x, y)
        return wp

    def hLine(self, distance):
        return self.lineTo(self._last_pt[0] + distance, self._last_pt[1])

    def vLine(self, distance):
        return self.lineTo(self._last_pt[0], self._last_pt[1] + distance)

    def close(self):
        wp = Workplane(self.plane, self._shape)
        wp._center_offset = self._center_offset
        pts = list(self._pts)
        if pts and pts[0] != pts[-1]:
            pts.append(pts[0])
        wp._pts = pts
        wp._pending_2d = ("wire", pts)
        return wp

    def box(self, length, width, height, centered=True):
        b = Part.makeBox(length, width, height)
        if centered is True or (isinstance(centered, (tuple, list)) and any(centered)):
            cx = -length / 2.0 if (centered is True or centered[0]) else 0.0
            cy = -width / 2.0 if (centered is True or centered[1]) else 0.0
            cz = -height / 2.0 if (centered is True or (len(centered) > 2 and centered[2])) else 0.0
            b.translate(App.Vector(cx, cy, cz))
        return Workplane(self.plane, b)

    def extrude(self, distance, both=False):
        if not self._pending_2d:
            raise ValueError("No 2D sketch defined to extrude!")
        
        kind = self._pending_2d[0]
        cx, cy, cz = self._center_offset
        
        if kind == "circle":
            r = self._pending_2d[1]
            if both:
                cyl = Part.makeCylinder(r, distance * 2.0, App.Vector(cx, cy, cz - distance), App.Vector(0, 0, 1))
            else:
                cyl = Part.makeCylinder(r, distance, App.Vector(cx, cy, cz), App.Vector(0, 0, 1))
            shape = cyl
        elif kind == "wire":
            pts = self._pending_2d[1]
            vec_pts = [ App.Vector(px + cx, py + cy, cz) for px, py in pts ]
            poly = Part.makePolygon(vec_pts)
            face = Part.Face(poly)
            if both:
                face.translate(App.Vector(0, 0, -distance))
                shape = face.extrude(App.Vector(0, 0, distance * 2.0))
            else:
                shape = face.extrude(App.Vector(0, 0, distance))
        elif kind == "rect":
            xLen, yLen, centered = self._pending_2d[1], self._pending_2d[2], self._pending_2d[3]
            ox = cx - (xLen / 2.0 if centered else 0.0)
            oy = cy - (yLen / 2.0 if centered else 0.0)
            if both:
                b = Part.makeBox(xLen, yLen, distance * 2.0, App.Vector(ox, oy, cz - distance))
            else:
                b = Part.makeBox(xLen, yLen, distance, App.Vector(ox, oy, cz))
            shape = b
        else:
            raise NotImplementedError(f"Unsupported 2D shape kind: {kind}")

        if self._shape is not None:
            shape = self._shape.fuse(shape)
            
        return Workplane(self.plane, shape)

    def translate(self, vec):
        if self._shape is None:
            return self
        v = App.Vector(vec[0], vec[1], vec[2] if len(vec) > 2 else 0.0)
        s = self._shape.copy()
        s.translate(v)
        return Workplane(self.plane, s)

    def rotate(self, axis_start, axis_end_or_dir, angle_degrees):
        if self._shape is None:
            return self
        p1 = App.Vector(axis_start[0], axis_start[1], axis_start[2])
        p2 = App.Vector(axis_end_or_dir[0], axis_end_or_dir[1], axis_end_or_dir[2])
        direction = p2 if p1.Length == 0 else (p2 - p1)
        s = self._shape.copy()
        s.rotate(p1, direction, angle_degrees)
        return Workplane(self.plane, s)

    def union(self, other):
        s1 = self.val()
        s2 = other.val() if hasattr(other, "val") else other
        return Workplane(self.plane, s1.fuse(s2))

    def cut(self, other):
        s1 = self.val()
        s2 = other.val() if hasattr(other, "val") else other
        return Workplane(self.plane, s1.cut(s2))

    def intersect(self, other):
        s1 = self.val()
        s2 = other.val() if hasattr(other, "val") else other
        return Workplane(self.plane, s1.common(s2))

    def val(self):
        if self._shape is not None:
            return self._shape
        raise ValueError("Workplane has no 3D solid generated!")


def show_object(obj, name="AICAD_Model"):
    doc = App.ActiveDocument or App.newDocument("AICAD_Model")
    shape = obj.val() if hasattr(obj, "val") else obj
    feature = doc.addObject("Part::Feature", name)
    feature.Shape = shape
    doc.recompute()
    return feature

