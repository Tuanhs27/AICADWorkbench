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
import urllib.request
import urllib.error

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
6. Gán đối tượng mô hình cuối cùng vào biến 'r' và gọi show_object(r). Không đưa thêm giải thích bên ngoài khối mã."""

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
4. Always attach final shape:
   obj = doc.addObject("Part::Feature", "ObjectName")
   obj.Shape = final_shape
   doc.recompute()
5. Output ONLY executable Python code in ```python ... ``` block.
"""

class AICADEngine:
    def __init__(self, endpoint="http://127.0.0.1:11434", model="qwen2.5-coder:3b", mode="cadquery"):
        self.endpoint = endpoint.rstrip("/")
        self.model = model
        self.mode = mode # 'cadquery' or 'freecad'
        self.last_generated_code = ""
        self.last_error = ""

    def query_ollama(self, prompt, temperature=0.2):
        """Query Ollama generate API (http://localhost:11434/api/generate)"""
        url = f"{self.endpoint}/api/generate"
        
        # Format prompt according to selected mode
        if self.mode == "cadquery":
            sys_prompt = DEFAULT_CADQUERY_SYSTEM_PROMPT
            # Align with the cleaned dataset prefix
            if not prompt.startswith("Dựa vào mô tả sau đây") and not prompt.startswith("Please based on"):
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
        return {
            "name": obj.Name,
            "x": bbox.XMax - bbox.XMin,
            "y": bbox.YMax - bbox.YMin,
            "z": bbox.ZMax - bbox.ZMin,
            "volume": getattr(shape, "Volume", 0.0),
            "solids": len(getattr(shape, "Solids", [])),
            "faces": len(getattr(shape, "Faces", []))
        }

    def extract_code(self, response_text):
        """Extract Python code block from markdown response"""
        pattern = r"```(?:python)?\s*(.*?)\s*```"
        matches = re.findall(pattern, response_text, re.DOTALL | re.IGNORECASE)
        if matches:
            return matches[0].strip()
        return response_text.strip()

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

            # If CadQuery returned an object assigned to 'r'
            if "r" in exec_globals and exec_globals["r"] is not None:
                r_val = exec_globals["r"]
                cadquery_bridge.show_object(r_val, "AICAD_Model")

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

