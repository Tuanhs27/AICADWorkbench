# SPDX-License-Identifier: LGPL-2.1-or-later
"""
cadquery_bridge.py: High-fidelity CadQuery compatibility layer for FreeCAD.
Allows executing CadQuery scripts (from the cleaned Text-to-CAD dataset)
directly inside FreeCAD's OpenCASCADE engine with zero external dependencies,
supporting 2D sketches (wires, arcs, polylines, circles, rects, squares),
variadic boolean cuts (*others), unions, 3D extrusions, revolves, selectors,
and automatic cutting-tool generation.
"""

import math
import sys

try:
    import FreeCAD as App
    import Part
except ImportError:
    App = None
    Part = None


def _is_centered(centered, idx=0):
    """Safely determine if centered along a specific axis index (0=X, 1=Y, 2=Z)"""
    if isinstance(centered, (tuple, list)):
        return bool(centered[idx]) if idx < len(centered) else False
    return bool(centered)


def _flatten_shapes(args):
    """Flatten nested lists/tuples of shapes or Workplanes"""
    flat = []
    for a in args:
        if isinstance(a, (list, tuple)):
            flat.extend(_flatten_shapes(a))
        elif a is not None:
            flat.append(a)
    return flat


class Vector:
    """CadQuery Vector wrapper compatible with FreeCAD App.Vector"""
    def __init__(self, x=0.0, y=0.0, z=0.0):
        if isinstance(x, (tuple, list)):
            self.x = float(x[0])
            self.y = float(x[1]) if len(x) > 1 else 0.0
            self.z = float(x[2]) if len(x) > 2 else 0.0
        elif hasattr(x, "x") and hasattr(x, "y"):
            self.x = float(x.x)
            self.y = float(x.y)
            self.z = float(getattr(x, "z", 0.0))
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

    def __repr__(self):
        return f"Vector({self.x}, {self.y}, {self.z})"


def _make_cutting_tool(shape_2d_or_3d, target_solid):
    """
    If shape is already a 3D solid, return as is.
    If shape is a 2D Face or Wire, extrude it across target_solid bounding box
    so it cleanly penetrates and cuts through target_solid.
    """
    if Part is None or shape_2d_or_3d is None:
        return shape_2d_or_3d

    solids = getattr(shape_2d_or_3d, "Solids", [])
    if len(solids) > 0:
        return shape_2d_or_3d

    # Shape is 2D (Face or Wire)
    face = shape_2d_or_3d
    if len(getattr(shape_2d_or_3d, "Faces", [])) == 0 and len(getattr(shape_2d_or_3d, "Wires", [])) > 0:
        face = Part.Face(shape_2d_or_3d.Wires[0])

    if target_solid is not None and hasattr(target_solid, "BoundBox"):
        bbox = target_solid.BoundBox
        z_span = max(abs(bbox.ZMax - bbox.ZMin), 10.0)
        z_min = bbox.ZMin - z_span * 0.5 - 5.0
        z_len = z_span * 2.0 + 10.0
    else:
        z_min = -500.0
        z_len = 1000.0

    cutter = face.copy()
    cutter.translate(App.Vector(0, 0, z_min))
    return cutter.extrude(App.Vector(0, 0, z_len))


class Workplane:
    def __init__(self, plane="XY", shape=None, center_offset=None, selected_face=None):
        self.plane = plane
        self._shape = shape
        self._center_offset = center_offset if center_offset is not None else (0.0, 0.0, 0.0)
        self._cur_pt = (0.0, 0.0)
        self._pts = []
        self._edges = []
        self._selected_face = selected_face
        self._pending_2d = None  # ("circle", r) or ("rect", w, h, centered) or ("face", Part.Face)
        self._pushed_points = []

    def center(self, x, y):
        wp = self._clone()
        wp._center_offset = (
            wp._center_offset[0] + float(x),
            wp._center_offset[1] + float(y),
            wp._center_offset[2]
        )
        return wp

    def transformed(self, offset=(0, 0, 0), rotate=(0, 0, 0)):
        wp = self._clone()
        ox = wp._center_offset[0] + (float(offset[0]) if len(offset) > 0 else 0.0)
        oy = wp._center_offset[1] + (float(offset[1]) if len(offset) > 1 else 0.0)
        oz = wp._center_offset[2] + (float(offset[2]) if len(offset) > 2 else 0.0)
        wp._center_offset = (ox, oy, oz)
        return wp

    def pushPoints(self, points):
        wp = self._clone()
        wp._pushed_points = list(points)
        return wp

    def _clone(self):
        wp = Workplane(self.plane, self._shape, self._center_offset, self._selected_face)
        wp._cur_pt = self._cur_pt
        wp._pts = list(self._pts)
        wp._edges = list(self._edges)
        wp._pending_2d = self._pending_2d
        wp._pushed_points = list(self._pushed_points)
        return wp

    # ---------------- 2D Sketch Drawing ---------------- #

    def moveTo(self, x, y, z=0.0):
        wp = self._clone()
        wp._cur_pt = (float(x), float(y))
        wp._pts = [(float(x), float(y))]
        wp._edges = []
        return wp

    def lineTo(self, x, y, z=0.0):
        wp = self._clone()
        cx, cy, cz = wp._center_offset
        p1 = App.Vector(wp._cur_pt[0] + cx, wp._cur_pt[1] + cy, cz)
        p2 = App.Vector(float(x) + cx, float(y) + cy, cz)
        if (p2 - p1).Length > 1e-6 and Part is not None:
            edge = Part.LineSegment(p1, p2).toShape()
            wp._edges.append(edge)
        wp._cur_pt = (float(x), float(y))
        wp._pts.append((float(x), float(y)))
        return wp

    def hLine(self, distance):
        return self.lineTo(self._cur_pt[0] + float(distance), self._cur_pt[1])

    def vLine(self, distance):
        return self.lineTo(self._cur_pt[0], self._cur_pt[1] + float(distance))

    def threePointArc(self, pt_mid, pt_end):
        wp = self._clone()
        cx, cy, cz = wp._center_offset
        p1 = App.Vector(wp._cur_pt[0] + cx, wp._cur_pt[1] + cy, cz)
        p2 = App.Vector(float(pt_mid[0]) + cx, float(pt_mid[1]) + cy, cz)
        p3 = App.Vector(float(pt_end[0]) + cx, float(pt_end[1]) + cy, cz)
        if Part is not None:
            try:
                arc = Part.Arc(p1, p2, p3)
                edge = Part.Edge(arc)
                wp._edges.append(edge)
            except Exception:
                edge = Part.LineSegment(p1, p3).toShape()
                wp._edges.append(edge)
        wp._cur_pt = (float(pt_end[0]), float(pt_end[1]))
        wp._pts.append(wp._cur_pt)
        return wp

    def polyline(self, points):
        wp = self._clone()
        if not points:
            return wp
        wp = wp.moveTo(points[0][0], points[0][1])
        for pt in points[1:]:
            wp = wp.lineTo(pt[0], pt[1])
        return wp

    def close(self):
        wp = self._clone()
        if not wp._edges and len(wp._pts) >= 3:
            cx, cy, cz = wp._center_offset
            vec_pts = [App.Vector(px + cx, py + cy, cz) for px, py in wp._pts]
            if vec_pts[0] != vec_pts[-1]:
                vec_pts.append(vec_pts[0])
            poly = Part.makePolygon(vec_pts)
            face = Part.Face(poly)
            wp._pending_2d = ("face", face)
            return wp

        if wp._edges:
            cx, cy, cz = wp._center_offset
            first_pt = App.Vector(wp._pts[0][0] + cx, wp._pts[0][1] + cy, cz)
            last_pt = App.Vector(wp._cur_pt[0] + cx, wp._cur_pt[1] + cy, cz)
            if (first_pt - last_pt).Length > 1e-6 and Part is not None:
                wp._edges.append(Part.LineSegment(last_pt, first_pt).toShape())
            try:
                wire = Part.Wire(wp._edges)
                face = Part.Face(wire)
                wp._pending_2d = ("face", face)
            except Exception:
                pass
        return wp

    def circle(self, radius):
        wp = self._clone()
        wp._pending_2d = ("circle", float(radius))
        return wp

    def rect(self, xLen, yLen, centered=True):
        wp = self._clone()
        wp._pending_2d = ("rect", float(xLen), float(yLen), centered)
        return wp

    def square(self, length, centered=True):
        """CadQuery square alias for rect(length, length)"""
        return self.rect(length, length, centered=centered)

    # ---------------- 3D Primitives & Operations ---------------- #

    def box(self, length, width, height, centered=True):
        if Part is None:
            return self
        length, width, height = float(length), float(width), float(height)
        b = Part.makeBox(length, width, height)
        cx = -length / 2.0 if _is_centered(centered, 0) else 0.0
        cy = -width / 2.0 if _is_centered(centered, 1) else 0.0
        cz = -height / 2.0 if _is_centered(centered, 2) else 0.0
        b.translate(App.Vector(cx, cy, cz))

        ox, oy, oz = self._center_offset
        if ox != 0.0 or oy != 0.0 or oz != 0.0:
            b.translate(App.Vector(ox, oy, oz))
        return Workplane(self.plane, b, self._center_offset)

    def cylinder(self, height, radius, centered=True):
        if Part is None:
            return self
        height, radius = float(height), float(radius)
        c = Part.makeCylinder(radius, height)
        if _is_centered(centered, 2):
            c.translate(App.Vector(0, 0, -height / 2.0))
        ox, oy, oz = self._center_offset
        if ox != 0.0 or oy != 0.0 or oz != 0.0:
            c.translate(App.Vector(ox, oy, oz))
        return Workplane(self.plane, c, self._center_offset)

    def sphere(self, radius):
        if Part is None:
            return self
        s = Part.makeSphere(float(radius))
        ox, oy, oz = self._center_offset
        if ox != 0.0 or oy != 0.0 or oz != 0.0:
            s.translate(App.Vector(ox, oy, oz))
        return Workplane(self.plane, s, self._center_offset)

    def _build_2d_shape(self):
        """Construct a Part.Face from pending 2D sketch"""
        if not self._pending_2d or Part is None:
            return None
        kind = self._pending_2d[0]
        cx, cy, cz = self._center_offset

        if kind == "circle":
            r = self._pending_2d[1]
            if self._pushed_points:
                faces = []
                for px, py in self._pushed_points:
                    c = Part.makeCircle(r, App.Vector(px + cx, py + cy, cz), App.Vector(0, 0, 1))
                    faces.append(Part.Face(Part.Wire([Part.Edge(c)])))
                return Part.Compound(faces) if len(faces) > 1 else faces[0]
            else:
                c = Part.makeCircle(r, App.Vector(cx, cy, cz), App.Vector(0, 0, 1))
                w = Part.Wire([Part.Edge(c)])
                return Part.Face(w)
        elif kind == "face":
            return self._pending_2d[1]
        elif kind == "rect":
            xLen, yLen, centered = self._pending_2d[1], self._pending_2d[2], self._pending_2d[3]
            ox = cx - (xLen / 2.0 if _is_centered(centered, 0) else 0.0)
            oy = cy - (yLen / 2.0 if _is_centered(centered, 1) else 0.0)
            poly = Part.makePolygon([
                App.Vector(ox, oy, cz),
                App.Vector(ox + xLen, oy, cz),
                App.Vector(ox + xLen, oy + yLen, cz),
                App.Vector(ox, oy + yLen, cz),
                App.Vector(ox, oy, cz)
            ])
            return Part.Face(poly)
        return None

    def extrude(self, distance, both=False):
        if Part is None:
            return self
        distance = float(distance)

        # 1. If self already holds a 2D Face/Wire shape
        if self._shape is not None and len(getattr(self._shape, "Solids", [])) == 0:
            if both:
                s = self._shape.copy()
                s.translate(App.Vector(0, 0, -distance))
                return Workplane(self.plane, s.extrude(App.Vector(0, 0, distance * 2.0)), self._center_offset)
            else:
                return Workplane(self.plane, self._shape.extrude(App.Vector(0, 0, distance)), self._center_offset)

        # 2. Otherwise extrude from pending 2D sketch
        face_2d = self._build_2d_shape()
        if face_2d is None:
            raise ValueError("No 2D sketch defined to extrude!")

        if both:
            face_2d.translate(App.Vector(0, 0, -distance))
            shape = face_2d.extrude(App.Vector(0, 0, distance * 2.0))
        else:
            shape = face_2d.extrude(App.Vector(0, 0, distance))

        if self._shape is not None:
            shape = self._shape.fuse(shape)

        return Workplane(self.plane, shape, self._center_offset)

    def revolve(self, angleDegrees=360.0, axisStart=(0, 0, 0), axisEnd=(0, 0, 1)):
        face_2d = self._build_2d_shape() or self.val()
        p1 = App.Vector(axisStart[0], axisStart[1], axisStart[2])
        p2 = App.Vector(axisEnd[0], axisEnd[1], axisEnd[2])
        v_dir = p2 - p1 if p1.Length > 0 else p2
        shape = face_2d.revolve(p1, v_dir, float(angleDegrees))
        return Workplane(self.plane, shape, self._center_offset)

    def faces(self, selector=">Z"):
        """Select face by direction, e.g. >Z, <Z, >X, <X, >Y, <Y"""
        if self._shape is None or not hasattr(self._shape, "Faces") or not self._shape.Faces:
            return self

        sel = selector.strip().upper()
        faces = self._shape.Faces

        if sel == ">Z":
            target = max(faces, key=lambda f: f.CenterOfMass.z)
        elif sel == "<Z":
            target = min(faces, key=lambda f: f.CenterOfMass.z)
        elif sel == ">X":
            target = max(faces, key=lambda f: f.CenterOfMass.x)
        elif sel == "<X":
            target = min(faces, key=lambda f: f.CenterOfMass.x)
        elif sel == ">Y":
            target = max(faces, key=lambda f: f.CenterOfMass.y)
        elif sel == "<Y":
            target = min(faces, key=lambda f: f.CenterOfMass.y)
        else:
            target = faces[0]

        return Workplane(self.plane, self._shape, self._center_offset, selected_face=target)

    def solids(self):
        return self

    def edges(self):
        return getattr(self.val(), "Edges", [])

    def vertices(self):
        return getattr(self.val(), "Vertexes", [])

    def workplane(self, offset=0.0, centerOption="ProjectedCenter", invert=False):
        wp = self._clone()
        if self._selected_face is not None:
            cm = self._selected_face.CenterOfMass
            wp._center_offset = (cm.x, cm.y, cm.z + float(offset))
        return wp

    def cutThruAll(self):
        if self._shape is None:
            raise ValueError("No 3D solid to cut through!")
        face_2d = self._build_2d_shape()
        if face_2d is None:
            raise ValueError("No 2D sketch defined for cutThruAll!")
        cutter = _make_cutting_tool(face_2d, self._shape)
        result = self._shape.cut(cutter)
        return Workplane(self.plane, result, self._center_offset)

    def cutBlind(self, distance):
        if self._shape is None:
            raise ValueError("No 3D solid to cut!")
        face_2d = self._build_2d_shape()
        if face_2d is None:
            raise ValueError("No 2D sketch defined for cutBlind!")
        cutter = face_2d.extrude(App.Vector(0, 0, -float(distance)))
        result = self._shape.cut(cutter)
        return Workplane(self.plane, result, self._center_offset)

    def hole(self, diameter, depth=None):
        if self._shape is None:
            raise ValueError("No 3D solid to drill hole!")
        radius = float(diameter) / 2.0
        wp = self.circle(radius)
        if depth is None:
            return wp.cutThruAll()
        else:
            return wp.cutBlind(depth)

    def cboreHole(self, diameter, cboreDiameter, cboreDepth, depth=None):
        wp = self.hole(diameter, depth)
        return wp.hole(cboreDiameter, cboreDepth)

    def cskHole(self, diameter, cskDiameter, cskAngle, depth=None):
        return self.hole(diameter, depth)

    def fillet(self, radius):
        s = self.val()
        try:
            res = s.makeFillet(float(radius), s.Edges)
            return Workplane(self.plane, res, self._center_offset)
        except Exception:
            return self

    def chamfer(self, length):
        s = self.val()
        try:
            res = s.makeChamfer(float(length), s.Edges)
            return Workplane(self.plane, res, self._center_offset)
        except Exception:
            return self

    def scale(self, factor):
        s = self.val()
        s_copy = s.copy()
        s_copy.scale(float(factor), App.Vector(0, 0, 0))
        return Workplane(self.plane, s_copy, self._center_offset)

    # ---------------- Transformations & Booleans ---------------- #

    def translate(self, vec):
        s = self.val()
        if hasattr(vec, "to_fc"):
            v = vec.to_fc()
        elif hasattr(vec, "x") and hasattr(vec, "y"):
            v = App.Vector(vec.x, vec.y, getattr(vec, "z", 0.0))
        elif isinstance(vec, (tuple, list)):
            v = App.Vector(float(vec[0]), float(vec[1]), float(vec[2]) if len(vec) > 2 else 0.0)
        else:
            v = App.Vector(0, 0, 0)
        s_copy = s.copy()
        s_copy.translate(v)
        return Workplane(self.plane, s_copy, self._center_offset)

    def rotate(self, axis_start, axis_end_or_dir, angle_degrees):
        s = self.val()
        p1 = App.Vector(axis_start[0], axis_start[1], axis_start[2])
        p2 = App.Vector(axis_end_or_dir[0], axis_end_or_dir[1], axis_end_or_dir[2])
        direction = p2 if p1.Length == 0 else (p2 - p1)
        s_copy = s.copy()
        s_copy.rotate(p1, direction, float(angle_degrees))
        return Workplane(self.plane, s_copy, self._center_offset)

    def union(self, *others, **kwargs):
        """Boolean Union supporting variadic arguments: union(o1, o2, o3) or union([o1, o2])"""
        current_shape = self.val()
        flat = _flatten_shapes(others)
        for item in flat:
            s2 = item.val() if hasattr(item, "val") else item
            if s2 is not None:
                current_shape = current_shape.fuse(s2)
        return Workplane(self.plane, current_shape, self._center_offset)

    def add(self, *others, **kwargs):
        return self.union(*others, **kwargs)

    def combine(self):
        return self

    def cut(self, *others, **kwargs):
        """Boolean Cut supporting variadic arguments: cut(c1, c2, c3, c4) or cut([c1, c2])"""
        flat = _flatten_shapes(others)
        if not flat:
            return self

        current_shape = self.val()
        for item in flat:
            s2 = item.val() if hasattr(item, "val") else item
            if s2 is None:
                continue

            s1_is_solid = len(getattr(current_shape, "Solids", [])) > 0
            s2_is_solid = len(getattr(s2, "Solids", [])) > 0

            if s1_is_solid and not s2_is_solid:
                cutter = _make_cutting_tool(s2, current_shape)
                current_shape = current_shape.cut(cutter)
            elif not s1_is_solid and s2_is_solid:
                cutter = s2
                current_shape = current_shape.cut(cutter)
            else:
                # Both 3D solids or both 2D faces
                current_shape = current_shape.cut(s2)

        return Workplane(self.plane, current_shape, self._center_offset)

    def intersect(self, *others, **kwargs):
        """Boolean Intersection supporting variadic arguments: intersect(o1, o2)"""
        flat = _flatten_shapes(others)
        if not flat:
            return self
        current_shape = self.val()
        for item in flat:
            s2 = item.val() if hasattr(item, "val") else item
            if s2 is not None:
                current_shape = current_shape.common(s2)
        return Workplane(self.plane, current_shape, self._center_offset)

    def val(self):
        if self._shape is not None:
            return self._shape
        shape_2d = self._build_2d_shape()
        if shape_2d is not None:
            self._shape = shape_2d
            return self._shape
        raise ValueError("Workplane has no 3D solid or 2D sketch generated!")

    def all(self):
        return [self.val()]

    def vals(self):
        return [self.val()]

    @property
    def objects(self):
        return [self.val()]


def show_object(obj, name="AICAD_Model"):
    """Render CadQuery Workplane or FreeCAD Shape into Active Document"""
    if App is None:
        return None

    doc = App.ActiveDocument
    if doc is None:
        doc = App.newDocument("AICAD_Model")

    shape = obj.val() if hasattr(obj, "val") else obj
    if shape is None:
        return None

    fc_obj = doc.getObject(name)
    if fc_obj is None:
        fc_obj = doc.addObject("Part::Feature", name)

    fc_obj.Shape = shape
    doc.recompute()
    return fc_obj
