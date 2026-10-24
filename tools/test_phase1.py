import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, r"c:\Users\tuanhs\AppData\Roaming\FreeCAD\v1-1\Mod\AICADWorkbench")
import FreeCAD as App
import aicad_engine
import aicad_gui

engine = aicad_engine.AICADEngine()

# Test 1: build_modification_prompt
p = engine.build_modification_prompt("Thêm lỗ tâm 20mm", "plate = cq.Workplane('XY').box(80, 80, 10)")
print("Test 1 (build_modification_prompt): SUCCESS, length =", len(p))

# Test 2: direct parametric modifiers
doc = App.newDocument("Phase1Test")
box = App.ActiveDocument.addObject("Part::Feature", "AICAD_Model")
import Part
box.Shape = Part.makeBox(80, 80, 10)
doc.recompute()

s1, m1 = engine.add_center_hole(20.0)
print("Test 2 (add_center_hole):", s1, m1)

s2, m2 = engine.adjust_model_thickness(25.0)
print("Test 3 (adjust_model_thickness):", s2, m2)

s3, m3 = engine.fillet_model_edges(2.0)
print("Test 4 (fillet_model_edges):", s3, m3)

stats = engine.get_model_geometry_stats()
print("Test 5 (get_model_geometry_stats):", stats)

