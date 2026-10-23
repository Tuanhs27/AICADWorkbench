import sys
import os

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import FreeCAD as App
import aicad_engine

e = aicad_engine.AICADEngine()

# Test 1: CadQuery script from cleaned dataset
cq_code = """import cadquery as cq
workplane = cq.Workplane("XY")
sketch = workplane.center(0.02, 0.02).circle(0.02)
cylinder = sketch.extrude(0.5)
r = cylinder
"""
s1, m1 = e.execute_code(cq_code)
print(f"Test 1 (CadQuery script): Success={s1}, Message={m1}")

# Test 2: Native FreeCAD script
fc_code = """import FreeCAD as App, Part
doc = App.ActiveDocument or App.newDocument('TestNative')
box = Part.makeBox(40, 30, 20)
obj = doc.addObject('Part::Feature', 'BoxNative')
obj.Shape = box
doc.recompute()
"""
s2, m2 = e.execute_code(fc_code)
print(f"Test 2 (Native FreeCAD script): Success={s2}, Message={m2}")

doc = App.ActiveDocument
print(f"Total objects in document: {len(doc.Objects)}")
for o in doc.Objects:
    print(f" - Object: {o.Name}, Shape Faces: {len(o.Shape.Faces)}, Volume: {o.Shape.Volume:.4f}")
