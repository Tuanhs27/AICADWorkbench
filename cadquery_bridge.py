# SPDX-License-Identifier: LGPL-2.1-or-later
"""
cadquery_bridge.py: High-fidelity CadQuery compatibility layer for FreeCAD.
Allows executing CadQuery scripts (from the cleaned Text-to-CAD dataset)
directly inside FreeCAD's OpenCASCADE engine with zero external dependencies,
supporting 2D sketches (wires, arcs, polylines, circles, rects), boolean cuts,
unions, 3D extrusions, selectors (.faces('>Z')), and auto-cutting tools.
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

    def _clone(self):
        wp = Workplane(self.plane, self._shape, self._center_offset, self._selected_face)
        wp._cur_pt = self._cur_pt
        wp._pts = list(self._pts)
        wp._edges = list(self._edges)
        wp._pending_2d = self._pending_2d
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
                # Fallback to straight segment if colinear
                edge = Part.LineSegment(p1, p3).toShape()
                wp._edges.append(edge)
        wp._cur_pt = (float(pt_end[0]), float(pt_end[1]))
        wp._pts.append(wp._cur_pt)
        return wp

    def polyline(self, points):
        wp = self._clone()
        if not points:
            return wp
        wp.moveTo(points[0][0], points[0][1])
        for pt in points[1:]:
            wp = wp.lineTo(pt[0], pt[1])
        return wp

    def close(self):
        wp = self._clone()
        if not wp._edges and len(wp._pts) >= 3:
            # Reconstruct polygon edges from points
            cx, cy, cz = wp._center_offset
            vec_pts = [App.Vector(px + cx, py + cy, cz) for px, py in wp._pts]
            if vec_pts[0] != vec_pts[-1]:
                vec_pts.append(vec_pts[0])
            poly = Part.makePolygon(vec_pts)
            face = Part.Face(poly)
            wp._pending_2d = ("face", face)
            return wp

        if wp._edges:
            # Check if start and end meet; if not, add closing line
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

    # ---------------- 3D Primitives & Operations ---------------- #

    def box(self, length, width, height, centered=True):
        if Part is None:
            return self
        length, width, height = float(length), float(width), float(height)
        b = Part.makeBox(length, width, height)
        if centered is True or (isinstance(centered, (tuple, list)) and any(centered)):
            cx = -length / 2.0 if (centered is True or centered[0]) else 0.0
            cy = -width / 2.0 if (centered is True or centered[1]) else 0.0
            cz = -height / 2.0 if (centered is True or (len(centered) > 2 and centered[2])) else 0.0
            b.translate(App.Vector(cx, cy, cz))
        # Account for center offset
        ox, oy, oz = self._center_offset
        if ox != 0.0 or oy != 0.0 or oz != 0.0:
            b.translate(App.Vector(ox, oy, oz))
        return Workplane(self.plane, b, self._center_offset)

    def _build_2d_shape(self):
        """Construct a Part.Face from pending 2D sketch"""
        if not self._pending_2d or Part is None:
            return None
        kind = self._pending_2d[0]
        cx, cy, cz = self._center_offset

        if kind == "circle":
            r = self._pending_2d[1]
            c = Part.makeCircle(r, App.Vector(cx, cy, cz), App.Vector(0, 0, 1))
            w = Part.Wire([Part.Edge(c)])
            return Part.Face(w)
        elif kind == "face":
            return self._pending_2d[1]
        elif kind == "rect":
            xLen, yLen, centered = self._pending_2d[1], self._pending_2d[2], self._pending_2d[3]
            ox = cx - (xLen / 2.0 if centered else 0.0)
            oy = cy - (yLen / 2.0 if centered else 0.0)
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

    def workplane(self, offset=0.0, centerOption="ProjectedCenter", invert=False):
        """Create new workplane referencing the selected face"""
        wp = self._clone()
        if self._selected_face is not None:
            cm = self._selected_face.CenterOfMass
            wp._center_offset = (cm.x, cm.y, cm.z + float(offset))
        return wp

    def cutThruAll(self):
        """Cut through entire shape using the pending 2D sketch"""
        if self._shape is None:
            raise ValueError("No 3D solid to cut through!")
        face_2d = self._build_2d_shape()
        if face_2d is None:
            raise ValueError("No 2D sketch defined for cutThruAll!")
        cutter = _make_cutting_tool(face_2d, self._shape)
        result = self._shape.cut(cutter)
        return Workplane(self.plane, result, self._center_offset)

    def cutBlind(self, distance):
        """Cut blind hole by distance into solid"""
        if self._shape is None:
            raise ValueError("No 3D solid to cut!")
        face_2d = self._build_2d_shape()
        if face_2d is None:
            raise ValueError("No 2D sketch defined for cutBlind!")
        distance = float(distance)
        cutter = face_2d.extrude(App.Vector(0, 0, -distance))
        result = self._shape.cut(cutter)
        return Workplane(self.plane, result, self._center_offset)

    def hole(self, diameter, depth=None):
        """Drill a hole of specified diameter and optional depth"""
        if self._shape is None:
            raise ValueError("No 3D solid to drill hole!")
        radius = float(diameter) / 2.0
        wp = self.circle(radius)
        if depth is None:
            return wp.cutThruAll()
        else:
            return wp.cutBlind(depth)

    def fillet(self, radius):
        """Fillet solid edges"""
        s = self.val()
        try:
            res = s.makeFillet(float(radius), s.Edges)
            return Workplane(self.plane, res, self._center_offset)
        except Exception:
            return self

    def chamfer(self, length):
        """Chamfer solid edges"""
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
        v = App.Vector(float(vec[0]), float(vec[1]), float(vec[2]) if len(vec) > 2 else 0.0)
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

    def union(self, other):
        s1 = self.val()
        s2 = other.val() if hasattr(other, "val") else other
        return Workplane(self.plane, s1.fuse(s2), self._center_offset)

    def add(self, other):
        return self.union(other)

    def combine(self):
        return self

    def cut(self, other):
        s1 = self.val()
        s2 = other.val() if hasattr(other, "val") else other

        # If s1 is a 3D solid and s2 is a 2D Face / Wire, auto-extrude s2 to cut cleanly
        s1_is_solid = len(getattr(s1, "Solids", [])) > 0
        s2_is_solid = len(getattr(s2, "Solids", [])) > 0

        if s1_is_solid and not s2_is_solid:
            cutter = _make_cutting_tool(s2, s1)
            result = s1.cut(cutter)
        else:
            result = s1.cut(s2)

        return Workplane(self.plane, result, self._center_offset)

    def intersect(self, other):
        s1 = self.val()
        s2 = other.val() if hasattr(other, "val") else other
        return Workplane(self.plane, s1.common(s2), self._center_offset)

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

    # Check if AICAD_Model already exists to update it cleanly without cluttering tree
    fc_obj = doc.getObject(name)
    if fc_obj is None:
        fc_obj = doc.addObject("Part::Feature", name)

    fc_obj.Shape = shape
    doc.recompute()
    return fc_obj
