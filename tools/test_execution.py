import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"c:\Users\tuanhs\AppData\Roaming\FreeCAD\v1-1\Mod\AICADWorkbench")
import FreeCAD as App
import aicad_engine

engine = aicad_engine.AICADEngine()

tests = [
    ("User Flange with 2D cuts", """
import cadquery as cq
workplane = cq.Workplane("XY")
outer_square = workplane.box(80, 80, 10, centered=(0, 0, 0))
circle = cq.Workplane("XY").center(4, 4).circle(4)
hole_1 = outer_square.cut(circle)
hole_2 = hole_1.cut(circle.translate((40, 0, 0)))
r = hole_2
show_object(r)
"""),
    ("Arc and Wire Extrusion", """
import cadquery as cq
wp = cq.Workplane("XY")
sketch = wp.moveTo(0.0, 0.0).lineTo(50.0, 0.0).threePointArc((60.0, 10.0), (50.0, 20.0)).lineTo(0.0, 20.0).close()
r = sketch.extrude(15.0)
show_object(r)
"""),
    ("Faces Selector and CutThruAll", """
import cadquery as cq
wp = cq.Workplane("XY")
body = wp.box(50, 50, 20)
r = body.faces(">Z").workplane().circle(10).cutThruAll()
show_object(r)
"""),
    ("Polyline and Close", """
import cadquery as cq
wp = cq.Workplane("XY")
r = wp.polyline([(0, 0), (30, 0), (30, 20), (15, 30), (0, 20)]).close().extrude(10)
show_object(r)
""")
]

for name, code in tests:
    doc = App.newDocument(name.replace(" ", "_"))
    success, msg = engine.execute_code(code)
    print(f"[{name}] Success: {success}")
    if not success:
        print(msg)
    else:
        obj = doc.getObject("AICAD_Model")
        print(f"[{name}] Shape Volume: {obj.Shape.Volume:.2f}, Faces: {len(obj.Shape.Faces)}")

