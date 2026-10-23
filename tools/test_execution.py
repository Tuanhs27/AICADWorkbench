import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"c:\Users\tuanhs\AppData\Roaming\FreeCAD\v1-1\Mod\AICADWorkbench")
import FreeCAD as App
import aicad_engine

engine = aicad_engine.AICADEngine()

# Test the exact code that caused: TypeError: Workplane.cut() takes 2 positional arguments but 5 were given
code_variadic_cut = """
import cadquery as cq

# Create a new workplane
r = cq.Workplane("XY")

# Define the square sketch
r = r.square(80, centered=(False, False))

# Define the circle for the holes
circle = cq.Workplane("XY").circle(4)

# Create the rectangular cutouts for the holes (passes 4 arguments to .cut())
r = r.cut(
    circle.translate((10, 10)),
    circle.translate((10, 70)),
    circle.translate((60, 10)),
    circle.translate((60, 70))
)

# Display the final model
show_object(r)
"""

doc1 = App.newDocument("TestVariadic2D")
success1, msg1 = engine.execute_code(code_variadic_cut)
print("Test 1 (2D variadic cut):", success1, msg1)
obj1 = doc1.getObject("AICAD_Model")
if obj1:
    print("  Obj1 Shape:", obj1.Shape, "Wires:", len(obj1.Shape.Wires))

# Test 3D extruded solid with variadic 2D cuts
code_variadic_cut_3d = """
import cadquery as cq

r = cq.Workplane("XY").square(80, centered=(False, False)).extrude(10)
circle = cq.Workplane("XY").circle(4)
r = r.cut(
    circle.translate((10, 10)),
    circle.translate((10, 70)),
    circle.translate((60, 10)),
    circle.translate((60, 70))
)
show_object(r)
"""

doc2 = App.newDocument("TestVariadic3D")
success2, msg2 = engine.execute_code(code_variadic_cut_3d)
print("Test 2 (3D solid with variadic 2D cuts):", success2, msg2)
obj2 = doc2.getObject("AICAD_Model")
if obj2:
    print("  Obj2 Volume:", obj2.Shape.Volume, "Faces:", len(obj2.Shape.Faces), "Solids:", len(obj2.Shape.Solids))
