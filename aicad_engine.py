# SPDX-License-Identifier: LGPL-2.1-or-later
"""
AICAD Engine: Handles prompt templating, Ollama communication,
code extraction, execution in FreeCAD, and error feedback.
Supports both Native FreeCAD Part scripts and CadQuery SFT scripts (Cleaned Dataset).
"""

import os
import re
import sys
import json
import math
import urllib.request
import urllib.error

_DLL_COOKIES = []
try:
    import FreeCAD as App
    import FreeCADGui as Gui
    import Part
except ImportError:
    FREECAD_PATHS = [
        r"C:\Program Files\FreeCAD 1.1\bin",
        r"C:\Program Files\FreeCAD 1.1\lib",
        r"C:\Program Files\FreeCAD 1.0\bin",
        r"C:\Program Files\FreeCAD 0.21\bin",
    ]
    for p in FREECAD_PATHS:
        if os.path.exists(p):
            if hasattr(os, "add_dll_directory"):
                try:
                    _DLL_COOKIES.append(os.add_dll_directory(p))
                except Exception:
                    pass
            os.environ["PATH"] = p + ";" + os.environ.get("PATH", "")
            if p not in sys.path:
                sys.path.insert(0, p)
    try:
        import FreeCAD as App
        import FreeCADGui as Gui
        import Part
    except ImportError:
        App = None
        Gui = None
        Part = None

import cadquery_bridge

# Register cadquery_bridge as 'cadquery' in sys.modules so 'import cadquery as cq' works seamlessly
if "cadquery" not in sys.modules:
    try:
        import cadquery
    except ImportError:
        sys.modules["cadquery"] = cadquery_bridge

DEFAULT_CADQUERY_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên tạo mã CadQuery (Python) để thiết kế mô hình 3D cơ khí chính xác cho FreeCAD.
Dựa vào mô tả của người dùng, hãy sinh mã CadQuery chuẩn xác, ngắn gọn trong khối ```python ... ```.

QUY TẮC CỐT LÕI:
1. Luôn sử dụng CHÍNH XÁC các kích thước milimet (mm) người dùng yêu cầu. TUYỆT ĐỐI KHÔNG dùng kích thước chuẩn hóa 0.75 hay 0.1 trừ khi người dùng chỉ định.
2. Với hình tròn hoặc lỗ tròn: dùng .circle(radius) với bán kính = đường kính / 2.0.
3. Khi tạo khối trụ bậc:
   base = cq.Workplane('XY').circle(r1).extrude(h1)
   top = cq.Workplane('XY').workplane(offset=h1).circle(r2).extrude(h2)
   r = base.union(top)
4. Khi tạo tấm hoặc mặt bích có nhiều lỗ bu-lông:
   plate = cq.Workplane('XY').box(length, width, height)
   holes = cq.Workplane('XY').pushPoints(pts).circle(hole_radius).extrude(height * 2, both=True)
   r = plate.cut(holes)
5. Khi tạo ống tròn rỗng:
   outer = cq.Workplane('XY').circle(r_outer).extrude(h)
   inner = cq.Workplane('XY').circle(r_inner).extrude(h + 10, both=True)
   r = outer.cut(inner)
6. Khi tạo puly rãnh V hoặc chi tiết tròn xoay (revolve):
   Vẽ nửa mặt cắt trên mặt phẳng XZ và xoay tròn 360 độ quanh trục Z:
   r = (cq.Workplane('XZ')
        .moveTo(r_in, -h/2)
        .lineTo(r_out, -h/2)
        .lineTo(r_out, -w_v)
        .lineTo(r_groove, 0)
        .lineTo(r_out, w_v)
        .lineTo(r_out, h/2)
        .lineTo(r_in, h/2)
        .close()
        .revolve(360, (0, 0, 0), (0, 0, 1)))
7. Gán đối tượng mô hình cuối cùng vào biến 'r' và gọi show_object(r). Không đưa thêm giải thích bên ngoài khối mã."""

DEFAULT_2D_SKETCH_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên tạo bản phác thảo biên dạng 2D cơ khí phẳng kín (Sketch Contour) cho FreeCAD bằng CadQuery.
QUY TẮC CỐT LÕI (BƯỚC 1: DỰNG HÌNH 2D):
1. TUYỆT ĐỐI KHÔNG ĐÙN 3D (.extrude) hay tạo khối hộp 3D (.box) hay .cylinder() hay xoay tròn 3D (.revolve). ĐÂY LÀ BƯỚC PHÁC THẢO 2D PHẲNG.
2. Dùng đúng mặt phẳng được chỉ định ('XY', 'XZ', hoặc 'YZ').
3. Dùng các lệnh vẽ 2D chuẩn:
   - Với hình tròn: .circle(radius) với bán kính = đường kính / 2.0.
   - Với hình chữ nhật: .rect(width, height)
   - Với mặt cắt puly hoặc trục bậc: vẽ nửa mặt cắt trên 'XZ' dùng .moveTo(), .lineTo(), và kết thúc bằng .close().
4. Gán đối tượng 2D vào biến 'r' và gọi show_object(r).
5. Chỉ xuất khối mã ```python ... ``` duy nhất, không giải thích."""

DEFAULT_MODIFICATION_SYSTEM_PROMPT = """Bạn là trợ lý AI chuyên gia công và chỉnh sửa mã CadQuery 3D cho FreeCAD theo yêu cầu thiết kế của người dùng.
QUY TẮC:
1. Đọc kỹ mã CAD hiện tại và yêu cầu chỉnh sửa từ người dùng.
2. Áp dụng sửa đổi trực tiếp lên mô hình (ví dụ: thêm lỗ khoét .cut(), bo tròn .fillet(), vát mép .chamfer(), đổi kích thước, thêm hoa văn lỗ bu-lông).
3. Gán kết quả mô hình vào biến 'r' và gọi show_object(r).
4. Chỉ xuất mã python hoàn chỉnh trong khối ```python ... ```."""

DEFAULT_FREECAD_SYSTEM_PROMPT = """You are an expert FreeCAD Python developer.
Generate valid, mathematically precise, robust FreeCAD Python scripts using the `Part` module.

CRITICAL RULES:
1. Always import FreeCAD and Part:
   import FreeCAD as App
   import Part
2. Use active document or create one:
   doc = App.ActiveDocument or App.newDocument("AICAD_Model")
3. Precision with geometric dimensions and coordinates:
   - All 3D vectors App.Vector MUST have 3 coordinates (x, y, z).
   - Part.makeCylinder takes RADIUS, not diameter: radius = diameter / 2.0.
   - For vertical holes along Z, the cylinder direction vector MUST be App.Vector(0, 0, 1).
   - Hole positions with edge offsets:
     (offset, offset), (L - offset, offset), (offset, W - offset), (L - offset, W - offset).
   - Triangular rib / gusset:
     poly = Part.makePolygon([p1, p2, p3, p1])
     face = Part.Face(poly)
     rib = face.extrude(App.Vector(0, rib_thickness, 0))
4. Khi tạo puly rãnh V hoặc chi tiết tròn xoay (revolve):
   Vẽ mặt cắt trên mặt phẳng XZ và xoay quanh trục Z:
   poly = Part.makePolygon(pts)
   face = Part.Face(poly)
   final_shape = face.revolve(App.Vector(0, 0, 0), App.Vector(0, 0, 1), 360)
5. Always attach final shape:
   obj = doc.addObject("Part::Feature", "ObjectName")
   obj.Shape = final_shape
   doc.recompute()
6. Output ONLY executable Python code in ```python ... ``` block.
"""

class AICADEngine:
    def __init__(self, endpoint="http://127.0.0.1:11434", model="qwen2.5-coder:3b", mode="cadquery"):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.mode = mode # 'cadquery' or 'freecad'
        self.last_generated_code = ""
        self.last_error = ""

    def query_ollama(self, prompt, temperature=0.2, system_prompt=None):
        """Query Ollama generate API (http://localhost:11434/api/generate)"""
        url = f"{self.endpoint}/api/generate"
        
        # Format prompt according to selected mode & custom system prompt
        if system_prompt is not None:
            sys_prompt = system_prompt
            formatted_prompt = prompt
        elif self.mode == "cadquery":
            sys_prompt = DEFAULT_CADQUERY_SYSTEM_PROMPT
            # Align with the cleaned dataset prefix only for raw prompt
            if (not prompt.startswith("Dựa vào mô tả sau đây") 
                and not prompt.startswith("Please based on")
                and not prompt.startswith("Bạn là")
                and "QUY TẮC" not in prompt):
                formatted_prompt = f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{prompt}"
            else:
                formatted_prompt = prompt
        else:
            sys_prompt = DEFAULT_FREECAD_SYSTEM_PROMPT
            formatted_prompt = prompt

        payload = {
            "model": self.model,
            "prompt": formatted_prompt,
            "system": sys_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
                "num_predict": 1024
            }
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                result = json.loads(response.read().decode("utf-8"))
                return result.get("response", "")
        except urllib.error.URLError as e:
            raise RuntimeError(
                f"Không thể kết nối đến Ollama tại {self.endpoint}.\n"
                f"Hãy đảm bảo Ollama đang chạy! Chi tiết lỗi: {e}"
            )

    def get_available_models(self):
        """Fetch installed Ollama models from /api/tags"""
        url = f"{self.endpoint}/api/tags"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
                return models if models else ["cadquery-ai", "qwen2.5-coder:3b"]
        except Exception:
            return ["cadquery-ai", "qwen2.5-coder:3b"]

    def get_model_geometry_stats(self):
        """Calculate BoundingBox, volume, solids, and faces of the active CAD model"""
        if App is None or App.ActiveDocument is None:
            return None
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return None

        shape = obj.Shape
        bbox = shape.BoundBox
        if not getattr(bbox, "isValid", lambda: True)() or bbox.XMax < bbox.XMin or bbox.XMax == float("inf") or bbox.XMax == float("-inf"):
            return None

        return {
            "name": obj.Name,
            "x": max(0.0, bbox.XMax - bbox.XMin),
            "y": max(0.0, bbox.YMax - bbox.YMin),
            "z": max(0.0, bbox.ZMax - bbox.ZMin),
            "volume": max(0.0, getattr(shape, "Volume", 0.0)),
            "solids": len(getattr(shape, "Solids", [])),
            "faces": len(getattr(shape, "Faces", []))
        }

    def extract_code(self, response_text):
        """Extract Python code block from markdown response and clean indentation"""
        import textwrap
        pattern = r"```(?:python)?\s*(.*?)\s*```"
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
        code = matches[0].strip() if matches else response_text.strip()

        # Clean accidental leading spaces / indentation quirks from LLM tokens
        code = textwrap.dedent(code).strip()
        clean_lines = []
        for line in code.splitlines():
            s = line.lstrip(" ")
            # If line starts with non-nested statement, remove leading spaces to prevent IndentationError
            if s.startswith(("import ", "from ", "#", "r =", "show_object", "def ", "class ", "sketch =", "cylinder =", "box =", "outer =", "inner =", "plate =", "hole =", "holes =")):
                clean_lines.append(s)
            else:
                clean_lines.append(line)
        return "\n".join(clean_lines).strip()

    def execute_code(self, code_str):
        """Execute script (CadQuery or Native FreeCAD) within FreeCAD document context"""
        if not code_str:
            raise ValueError("Không có mã nguồn để thực thi!")

        # Ensure cadquery bridge is dynamically reloaded from disk
        import importlib
        try:
            import cadquery_bridge
            importlib.reload(cadquery_bridge)
        except Exception:
            pass
        sys.modules["cadquery"] = cadquery_bridge

        import math
        exec_globals = {
            "App": App,
            "FreeCAD": App,
            "Gui": Gui,
            "FreeCADGui": Gui,
            "cq": cadquery_bridge,
            "cadquery": cadquery_bridge,
            "show_object": cadquery_bridge.show_object,
            "math": math,
            "__name__": "__main__",
        }

        try:
            exec(code_str, exec_globals)

            # If CadQuery returned an object assigned to 'r' or standard fallback variable names
            found_obj = None
            for var_name in ("r", "result", "model", "cylinder", "sketch", "part", "solid"):
                if var_name in exec_globals and exec_globals[var_name] is not None:
                    found_obj = exec_globals[var_name]
                    break
            if found_obj is not None:
                cadquery_bridge.show_object(found_obj, "AICAD_Model")

            if App and App.ActiveDocument:
                App.ActiveDocument.recompute()
                try:
                    if hasattr(Gui, "SendMsgToActiveView"):
                        Gui.SendMsgToActiveView("ViewFit")
                    elif Gui.activeDocument() and hasattr(Gui.activeDocument(), "activeView"):
                        Gui.activeDocument().activeView().viewFit()
                except Exception:
                    pass

            self.last_error = ""
            return True, "Tạo mô hình 3D thành công!"
        except Exception as e:
            import traceback
            err = traceback.format_exc()
            self.last_error = err
            return False, f"Lỗi thực thi mã:\n{err}"

    def build_fix_prompt(self, user_prompt, failed_code, error_message):
        """Generate a prompt to self-correct a failed script"""
        return (
            f"Đoạn mã sau được sinh cho yêu cầu: \"{user_prompt}\"\n\n"
            f"```python\n{failed_code}\n```\n\n"
            f"Tuy nhiên khi chạy trong FreeCAD gặp lỗi:\n"
            f"{error_message}\n\n"
            f"Hãy phân tích nguyên nhân và xuất lại đoạn mã hoàn chỉnh đã sửa lỗi trong ```python ... ```."
        )

    def build_modification_prompt(self, edit_instruction, current_code):
        """Construct multi-turn modification prompt to update existing CAD code based on user request"""
        if self.mode == "cadquery":
            return (
                f"Dưới đây là mã CadQuery (Python) hiện tại của mô hình 3D đang hiển thị trên FreeCAD:\n"
                f"```python\n{current_code.strip()}\n```\n\n"
                f"YÊU CẦU CHỈNH SỬA THIẾT KẾ:\n"
                f"\"{edit_instruction.strip()}\"\n\n"
                f"HƯỚNG DẪN THỰC HIỆN:\n"
                f"1. Hãy điều chỉnh, sửa đổi hoặc bổ sung trực tiếp trên mã nguồn cũ để đáp ứng chính xác yêu cầu chỉnh sửa trên.\n"
                f"2. Giữ nguyên các phần không bị yêu cầu sửa đổi, tuân thủ các kích thước milimet (mm) chính xác.\n"
                f"3. Gán đối tượng kết quả cuối cùng vào biến 'r' và gọi show_object(r).\n"
                f"4. Chỉ xuất khối mã ```python ... ``` hoàn chỉnh, không kèm giải thích bên ngoài."
            )
        else:
            return (
                f"Below is the current FreeCAD Python script for the active 3D model:\n"
                f"```python\n{current_code.strip()}\n```\n\n"
                f"USER MODIFICATION REQUEST:\n"
                f"\"{edit_instruction.strip()}\"\n\n"
                f"INSTRUCTIONS:\n"
                f"1. Modify or extend the existing script to satisfy the modification request.\n"
                f"2. Preserve the working parts of the original model.\n"
                f"3. Attach the final shape to the active document and recompute.\n"
                f"4. Output ONLY the updated executable Python code inside a ```python ... ``` block."
            )

    def add_center_hole(self, diameter_mm):
        """Direct parametric modifier: Cut a cylindrical hole at center of mass"""
        if App is None or App.ActiveDocument is None or Part is None:
            return False, "Không có tài liệu FreeCAD đang mở!"
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return False, "Không tìm thấy vật thể 3D để khoét lỗ!"

        try:
            shape = obj.Shape
            cm = shape.CenterOfMass
            bbox = shape.BoundBox
            radius = float(diameter_mm) / 2.0
            z_min = bbox.ZMin - 10.0
            z_len = (bbox.ZMax - bbox.ZMin) + 20.0
            hole = Part.makeCylinder(radius, z_len, App.Vector(cm.x, cm.y, z_min), App.Vector(0, 0, 1))
            obj.Shape = shape.cut(hole)
            doc.recompute()
            return True, f"Đã khoét lỗ tròn tâm Ø{diameter_mm}mm thành công!"
        except Exception as e:
            return False, f"Lỗi khoét lỗ tâm: {e}"

    def adjust_model_thickness(self, target_thickness_mm):
        """Direct parametric modifier: Adjust model thickness along Z"""
        if App is None or App.ActiveDocument is None or Part is None:
            return False, "Không có tài liệu FreeCAD đang mở!"
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return False, "Không tìm thấy vật thể 3D!"

        try:
            shape = obj.Shape
            bbox = shape.BoundBox
            current_thickness = bbox.ZMax - bbox.ZMin
            if current_thickness <= 1e-4:
                # 2D face: extrude
                solid = shape.extrude(App.Vector(0, 0, float(target_thickness_mm)))
                obj.Shape = solid
            else:
                scale_z = float(target_thickness_mm) / current_thickness
                mat = App.Matrix()
                mat.scale(1.0, 1.0, scale_z)
                obj.Shape = shape.transformGeometry(mat)
            doc.recompute()
            return True, f"Đã điều chỉnh chiều dày Z thành {target_thickness_mm}mm!"
        except Exception as e:
            return False, f"Lỗi chỉnh chiều dày: {e}"

    def fillet_model_edges(self, radius_mm=2.0):
        """Direct parametric modifier: Fillet solid edges"""
        if App is None or App.ActiveDocument is None or Part is None:
            return False, "Không có tài liệu FreeCAD đang mở!"
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return False, "Không tìm thấy vật thể 3D!"

        try:
            shape = obj.Shape
            if not shape.Edges:
                return False, "Vật thể không có cạnh để bo!"
            res = shape.makeFillet(float(radius_mm), shape.Edges)
            obj.Shape = res
            doc.recompute()
            return True, f"Đã bo tròn các cạnh bán kính R{radius_mm}mm!"
        except Exception as e:
            return False, f"Lỗi bo tròn mép: {e}"

    def chamfer_model_edges(self, distance_mm=1.0):
        """Direct parametric modifier: Chamfer solid edges"""
        if App is None or App.ActiveDocument is None or Part is None:
            return False, "Không có tài liệu FreeCAD đang mở!"
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return False, "Không tìm thấy vật thể 3D!"

        try:
            shape = obj.Shape
            if not shape.Edges:
                return False, "Vật thể không có cạnh để vát!"
            res = shape.makeChamfer(float(distance_mm), shape.Edges)
            obj.Shape = res
            doc.recompute()
            return True, f"Đã vát mép các cạnh {distance_mm}mm (Chamfer) thành công!"
        except Exception as e:
            return False, f"Lỗi vát mép Chamfer: {e}"

    def set_model_color(self, color_name="Thép xám"):
        """Set visual appearance of the 3D model"""
        if Gui is None or App is None or App.ActiveDocument is None:
            return False, "Không có GUI FreeCAD!"
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "ViewObject"):
            return False, "Không tìm thấy đối tượng hiển thị!"

        colors = {
            "Thép xám": (0.65, 0.68, 0.72),
            "Đồng thau": (0.85, 0.65, 0.20),
            "Nhôm sáng": (0.82, 0.85, 0.88),
            "Nhựa xanh": (0.15, 0.55, 0.85),
            "Vàng kim": (0.95, 0.78, 0.15),
            "Đỏ kỹ thuật": (0.85, 0.25, 0.20)
        }
        rgb = colors.get(color_name, (0.7, 0.7, 0.7))
        try:
            obj.ViewObject.ShapeColor = rgb
            return True, f"Đã đổi màu hiển thị sang: {color_name}"
        except Exception as e:
            return False, f"Lỗi đổi màu: {e}"

    def build_2d_sketch_prompt(self, user_prompt, plane="XY"):
        """Prompt specifically for generating a pure 2D sketch/contour without 3D extrusion"""
        return (
            f"Bạn là chuyên gia phác thảo CAD 2D. Nhiệm vụ: Dựng bản phác thảo biên dạng phẳng 2D kín (Sketch Contour) trên mặt phẳng '{plane}'.\n\n"
            f"MÔ TẢ YÊU CẦU PHÁC THẢO 2D:\n"
            f"\"{user_prompt.strip()}\"\n\n"
            f"QUY TẮC CỐT LÕI (BƯỚC 1: DỰNG HÌNH 2D):\n"
            f"1. Sử dụng Workplane('{plane}'). Sử dụng các lệnh 2D chuẩn: .moveTo(), .lineTo(), .threePointArc(), .polyline(), .circle(), .rect(), .close().\n"
            f"2. TUYỆT ĐỐI KHÔNG ĐÙN 3D (.extrude) hay tạo khối hộp 3D (.box). Đây là bước dựng hình 2D phẳng để kiểm tra biên dạng hình học.\n"
            f"3. Chu trình phác thảo BẮT BUỘC phải khép kín bằng .close() hoặc tạo thành hình phẳng 2D kín.\n"
            f"4. Ví dụ phác thảo mặt cắt chi tiết tròn xoay (Puly, Trục bậc) trên mặt phẳng 'XZ':\n"
            f"   r = (cq.Workplane('XZ')\n"
            f"        .moveTo(r_in, -h/2)\n"
            f"        .lineTo(r_out, -h/2)\n"
            f"        .lineTo(r_out, -w_v)\n"
            f"        .lineTo(r_groove, 0)\n"
            f"        .lineTo(r_out, w_v)\n"
            f"        .lineTo(r_out, h/2)\n"
            f"        .lineTo(r_in, h/2)\n"
            f"        .close())\n"
            f"5. Ví dụ phác thảo biên dạng phẳng (Mặt bích, Tấm gá) trên mặt phẳng 'XY':\n"
            f"   r = cq.Workplane('XY').rect(80, 80)\n"
            f"6. Gán đối tượng 2D cuối cùng vào biến 'r' và gọi show_object(r).\n"
            f"7. Chỉ xuất khối mã ```python ... ``` hoàn chỉnh."
        )

    def extrude_active_2d(self, distance_mm):
        """Step 2: Extrude active 2D shape into a 3D solid"""
        if App is None or App.ActiveDocument is None or Part is None:
            return False, "Không có tài liệu FreeCAD đang mở!", ""
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return False, "Không tìm thấy biên dạng 2D để đùn khối!", ""

        try:
            shape = obj.Shape
            dist = float(distance_mm)
            norm = App.Vector(0, 0, 1)
            if hasattr(shape, "Faces") and shape.Faces:
                try:
                    norm = shape.Faces[0].normalAt(0, 0)
                except Exception:
                    pass
            solid = shape.extrude(norm * dist)
            obj.Shape = solid
            doc.recompute()
            try:
                if hasattr(Gui, "SendMsgToActiveView"):
                    Gui.SendMsgToActiveView("ViewFit")
            except Exception:
                pass
            snippet = f"\n# Bước 2: Đùn khối 3D (Extrude) dày {dist}mm:\nr = r.extrude({dist})\nshow_object(r)\n"
            return True, f"Đã đùn khối 3D thành công với chiều dày {dist}mm!", snippet
        except Exception as e:
            return False, f"Lỗi đùn khối 3D: {e}", ""

    def revolve_active_2d(self, angle_deg=360.0, axis="Z"):
        """Step 2: Revolve active 2D shape into a 3D revolved solid (pulley, shaft, cone)"""
        if App is None or App.ActiveDocument is None or Part is None:
            return False, "Không có tài liệu FreeCAD đang mở!", ""
        doc = App.ActiveDocument
        obj = doc.getObject("AICAD_Model")
        if obj is None and doc.Objects:
            obj = doc.Objects[-1]
        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            return False, "Không tìm thấy biên dạng 2D để xoay tròn!", ""

        try:
            shape = obj.Shape
            ang = float(angle_deg)
            if axis.upper() == "Y":
                v_axis = App.Vector(0, 1, 0)
            elif axis.upper() == "X":
                v_axis = App.Vector(1, 0, 0)
            else:
                v_axis = App.Vector(0, 0, 1)

            solid = shape.revolve(App.Vector(0, 0, 0), v_axis, ang)
            obj.Shape = solid
            doc.recompute()
            try:
                if hasattr(Gui, "SendMsgToActiveView"):
                    Gui.SendMsgToActiveView("ViewFit")
            except Exception:
                pass
            snippet = f"\n# Bước 2: Xoay tròn 3D (Revolve) quanh trục {axis} góc {ang}°:\nr = r.revolve({ang}, (0, 0, 0), {tuple(v_axis)})\nshow_object(r)\n"
            return True, f"Đã xoay tròn 3D thành công quanh trục {axis} góc {ang}°!", snippet
        except Exception as e:
            return False, f"Lỗi xoay tròn 3D: {e}", ""

    def synthesize_engineering_code(self, prompt, plane="XY", step="2d"):
        """
        Parametric synthesis for common engineering components (Pulley, Flange, Shaft, Bracket).
        Returns generated Python CadQuery code if prompt matches an engineering archetype, else None.
        """
        p = prompt.lower().strip()
        
        # 1. Pulley with V-groove (Puly đai thang rãnh V)
        if any(k in p for k in ["puly", "pulley", "đai thang", "rãnh v", "rãnh chữ v"]):
            m_dout = re.search(r'(?:đường kính ngoài|d_ngoai|ngoài)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            dout = float(m_dout.group(1)) if m_dout else 80.0
            
            m_h = re.search(r'(?:chiều dày|bề dày|dày)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            h = float(m_h.group(1)) if m_h else 25.0
            
            m_depth = re.search(r'(?:sâu|độ sâu)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            depth = float(m_depth.group(1)) if m_depth else 10.0
            
            m_ang = re.search(r'(?:góc)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            ang = float(m_ang.group(1)) if m_ang else 38.0
            
            m_shaft = re.search(r'(?:lỗ trục|trục tâm|tâm phi|phi)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            shaft = float(m_shaft.group(1)) if m_shaft else 15.0
            
            r_in = shaft / 2.0
            r_out = dout / 2.0
            r_groove = max(r_in + 2.0, r_out - depth)
            half_w = round(depth * math.tan(math.radians(ang / 2.0)), 2)
            
            if step == "2d":
                return (
                    f"import cadquery as cq\n\n"
                    f"# Bước 1: Phác thảo 2D nửa mặt cắt puly đai thang rãnh V trên mặt phẳng XZ\n"
                    f"r_in = {r_in}\n"
                    f"r_out = {r_out}\n"
                    f"h = {h}\n"
                    f"r_groove = {r_groove}\n"
                    f"half_w = {half_w}\n\n"
                    f"r = (\n"
                    f"    cq.Workplane('XZ')\n"
                    f"    .moveTo(r_in, -h / 2.0)\n"
                    f"    .lineTo(r_out, -h / 2.0)\n"
                    f"    .lineTo(r_out, -half_w)\n"
                    f"    .lineTo(r_groove, 0.0)\n"
                    f"    .lineTo(r_out, half_w)\n"
                    f"    .lineTo(r_out, h / 2.0)\n"
                    f"    .lineTo(r_in, h / 2.0)\n"
                    f"    .close()\n"
                    f")\n"
                    f"show_object(r)\n"
                )
            else:  # 3D
                return (
                    f"import cadquery as cq\n\n"
                    f"# Tạo Puly đai thang rãnh V 3D hoàn chỉnh bằng Revolve\n"
                    f"r_in = {r_in}\n"
                    f"r_out = {r_out}\n"
                    f"h = {h}\n"
                    f"r_groove = {r_groove}\n"
                    f"half_w = {half_w}\n\n"
                    f"r = (\n"
                    f"    cq.Workplane('XZ')\n"
                    f"    .moveTo(r_in, -h / 2.0)\n"
                    f"    .lineTo(r_out, -h / 2.0)\n"
                    f"    .lineTo(r_out, -half_w)\n"
                    f"    .lineTo(r_groove, 0.0)\n"
                    f"    .lineTo(r_out, half_w)\n"
                    f"    .lineTo(r_out, h / 2.0)\n"
                    f"    .lineTo(r_in, h / 2.0)\n"
                    f"    .close()\n"
                    f"    .revolve(360, (0, 0, 0), (0, 0, 1))\n"
                    f")\n"
                    f"show_object(r)\n"
                )

        # 2. Round Flange (Mặt bích tròn)
        if any(k in p for k in ["bích tròn", "flange tròn", "mặt bích tròn", "round flange"]) or ("mặt bích" in p and "tròn" in p):
            m_dout = re.search(r'(?:đường kính ngoài|d_ngoai|ngoài)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            dout = float(m_dout.group(1)) if m_dout else 100.0
            
            m_h = re.search(r'(?:chiều dày|bề dày|dày)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            h = float(m_h.group(1)) if m_h else 12.0
            
            m_nholes = re.search(r'(\d+)\s*lỗ', p)
            nholes = int(m_nholes.group(1)) if m_nholes else 6
            
            m_dhole = re.search(r'(?:lỗ bu-lông|lỗ bu lông|lỗ bulong|lỗ).*?đường kính\s*(\d+(?:\.\d+)?)', p)
            dhole = float(m_dhole.group(1)) if m_dhole else 6.0
            
            m_pcd = re.search(r'(?:vòng chia|đường kính chia|vòng chia đường kính)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            pcd = float(m_pcd.group(1)) if m_pcd else 70.0
            
            m_center = re.search(r'(?:lỗ trục|lỗ tâm|tâm phi|trục phi)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            dcenter = float(m_center.group(1)) if m_center else 30.0

            r_out = dout / 2.0
            r_center = dcenter / 2.0
            r_hole = dhole / 2.0
            r_pcd = pcd / 2.0

            if step == "2d":
                code = (
                    f"import cadquery as cq\nimport math\n\n"
                    f"# Bước 1: Phác thảo 2D biên dạng mặt bích tròn D{dout} có lỗ tâm D{dcenter}\n"
                    f"outer = cq.Workplane('XY').circle({r_out})\n"
                    f"inner = cq.Workplane('XY').circle({r_center})\n"
                    f"r = outer.cut(inner)\n"
                )
                if nholes > 0:
                    code += (
                        f"\n# {nholes} lỗ bu-lông phân bố đều trên vòng chia D{pcd}\n"
                        f"bolt_pts = [\n"
                        f"    ({r_pcd} * math.cos(2 * math.pi * i / {nholes}), {r_pcd} * math.sin(2 * math.pi * i / {nholes}))\n"
                        f"    for i in range({nholes})\n"
                        f"]\n"
                        f"bolt_holes = cq.Workplane('XY').pushPoints(bolt_pts).circle({r_hole})\n"
                        f"r = r.cut(bolt_holes)\n"
                    )
                code += "\nshow_object(r)\n"
                return code
            else:
                return (
                    f"import cadquery as cq\nimport math\n\n"
                    f"# Tạo Mặt bích tròn D{dout} dày {h}mm có {nholes} lỗ bu-lông trên vòng chia D{pcd}\n"
                    f"flange = cq.Workplane('XY').circle({r_out}).extrude({h})\n"
                    f"center_hole = cq.Workplane('XY').circle({r_center}).extrude({h * 2.0}, both=True)\n"
                    f"r = flange.cut(center_hole)\n\n"
                    f"bolt_pts = [\n"
                    f"    ({r_pcd} * math.cos(2 * math.pi * i / {nholes}), {r_pcd} * math.sin(2 * math.pi * i / {nholes}))\n"
                    f"    for i in range({nholes})\n"
                    f"]\n"
                    f"bolt_holes = cq.Workplane('XY').pushPoints(bolt_pts).circle({r_hole}).extrude({h * 2.0}, both=True)\n"
                    f"r = r.cut(bolt_holes)\n"
                    f"show_object(r)\n"
                )

        # 3. Square Flange / Base Plate (Mặt bích vuông / Tấm gá)
        if any(k in p for k in ["bích vuông", "mặt bích vuông", "tấm gá", "đế gá", "square flange"]):
            m_w = re.search(r'(?:kích thước|vuông|cạnh)?\s*(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)', p)
            if m_w:
                w, l = float(m_w.group(1)), float(m_w.group(2))
            else:
                m_dim = re.search(r'(?:vuông|rộng)\s*(\d+(?:\.\d+)?)', p)
                w = float(m_dim.group(1)) if m_dim else 80.0
                l = w

            m_h = re.search(r'(?:chiều dày|bề dày|dày)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            h = float(m_h.group(1)) if m_h else 10.0

            m_center = re.search(r'(?:lỗ tâm|tâm phi|phi)\s*[:=]?\s*(\d+(?:\.\d+)?)', p)
            dcenter = float(m_center.group(1)) if m_center else 0.0

            if step == "2d":
                code = f"import cadquery as cq\n\n# Bước 1: Phác thảo 2D mặt bích vuông {w}x{l}mm\n"
                code += f"r = cq.Workplane('XY').rect({w}, {l})\n"
                if dcenter > 0:
                    code += f"hole = cq.Workplane('XY').circle({dcenter / 2.0})\nr = r.cut(hole)\n"
                corner_offset_x = (w / 2.0) - 10.0
                corner_offset_y = (l / 2.0) - 10.0
                code += (
                    f"pts = [({corner_offset_x}, {corner_offset_y}), (-{corner_offset_x}, {corner_offset_y}), "
                    f"(-{corner_offset_x}, -{corner_offset_y}), ({corner_offset_x}, -{corner_offset_y})]\n"
                    f"holes = cq.Workplane('XY').pushPoints(pts).circle(2.5)\n"
                    f"r = r.cut(holes)\n"
                )
                code += "show_object(r)\n"
                return code
            else:
                code = (
                    f"import cadquery as cq\n\n"
                    f"# Tạo Mặt bích vuông {w}x{l}mm dày {h}mm có 4 lỗ bắt ốc góc\n"
                    f"plate = cq.Workplane('XY').box({w}, {l}, {h})\n"
                )
                if dcenter > 0:
                    code += f"center_hole = cq.Workplane('XY').circle({dcenter / 2.0}).extrude({h * 2}, both=True)\nplate = plate.cut(center_hole)\n"
                corner_offset_x = (w / 2.0) - 10.0
                corner_offset_y = (l / 2.0) - 10.0
                code += (
                    f"pts = [({corner_offset_x}, {corner_offset_y}), (-{corner_offset_x}, {corner_offset_y}), "
                    f"(-{corner_offset_x}, -{corner_offset_y}), ({corner_offset_x}, -{corner_offset_y})]\n"
                    f"holes = cq.Workplane('XY').pushPoints(pts).circle(2.5).extrude({h * 2}, both=True)\n"
                    f"r = plate.cut(holes)\nshow_object(r)\n"
                )
                return code

        return None

