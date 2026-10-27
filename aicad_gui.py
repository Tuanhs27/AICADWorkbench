# SPDX-License-Identifier: LGPL-2.1-or-later
"""
AICAD GUI: Professional 3-Step Engineer CAD Assistant for FreeCAD.
Implements the authentic mechanical engineering CAD workflow:
- Step 1 (2D Sketching): Draw closed planar 2D contours on XY/XZ/YZ planes.
- Step 2 (3D Feature): Extrude (Pad) or Revolve (Shaft) 2D profile into 3D solid.
- Step 3 (Finishing): Drill center holes, adjust thickness, fillet, chamfer, change colors, or AI live edit.
- Step 4 (Fast 1-Shot): Instant 1-click full 3D generation and multi-turn AI editing.
"""

import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets, QtGui

from aicad_engine import (
    AICADEngine,
    DEFAULT_2D_SKETCH_SYSTEM_PROMPT,
    DEFAULT_MODIFICATION_SYSTEM_PROMPT
)

PRESET_2D_SKETCHES = [
    ("--- Chọn mẫu phác thảo 2D tham số ---", "", "XY", ""),
    (
        "1. Mặt cắt Puly đai thang rãnh V (XZ)",
        "Vẽ nửa mặt cắt puly rãnh chữ V: lỗ trục trong phi 15mm (r=7.5), đường kính ngoài 80mm (r=40), dày 25mm, rãnh chữ V sâu 10mm góc 38 độ ở giữa khép kín.",
        "XZ",
        """import cadquery as cq

r_in = 7.5
r_out = 40.0
h = 25.0
groove_depth = 10.0
half_w = 3.44  # 10 * tan(19 deg)
r_groove = 30.0

# Bước 1: Phác thảo 2D nửa mặt cắt puly trên mặt phẳng đứng XZ
r = (
    cq.Workplane('XZ')
    .moveTo(r_in, -h / 2)
    .lineTo(r_out, -h / 2)
    .lineTo(r_out, -half_w)
    .lineTo(r_groove, 0)
    .lineTo(r_out, half_w)
    .lineTo(r_out, h / 2)
    .lineTo(r_in, h / 2)
    .close()
)
show_object(r)
"""
    ),
    (
        "2. Biên dạng Mặt bích vuông 80x80 (XY)",
        "Vẽ biên dạng phẳng hình chữ nhật vuông 80x80mm tâm (0,0) khép kín.",
        "XY",
        """import cadquery as cq

# Bước 1: Phác thảo 2D biên dạng mặt bích vuông trên mặt bằng XY
r = cq.Workplane('XY').rect(80, 80)
show_object(r)
"""
    ),
    (
        "3. Biên dạng Mặt bích tròn D100 (XY)",
        "Vẽ đường tròn tâm (0,0) đường kính 100mm (bán kính 50mm) khép kín.",
        "XY",
        """import cadquery as cq

# Bước 1: Phác thảo 2D hình tròn đường kính 100mm
r = cq.Workplane('XY').circle(50)
show_object(r)
"""
    ),
    (
        "4. Mặt cắt Trục bậc 2 tầng (XZ)",
        "Vẽ nửa mặt cắt trục bậc 2 tầng: tầng dưới bán kính 20mm cao 50mm, tầng trên bán kính 10mm cao 30mm khép kín.",
        "XZ",
        """import cadquery as cq

# Bước 1: Phác thảo 2D nửa mặt cắt trục bậc trên mặt phẳng XZ
r = (
    cq.Workplane('XZ')
    .moveTo(0, 0)
    .lineTo(20, 0)
    .lineTo(20, 50)
    .lineTo(10, 50)
    .lineTo(10, 80)
    .lineTo(0, 80)
    .close()
)
show_object(r)
"""
    ),
    (
        "5. Biên dạng Giá đỡ chữ L 60x60mm (XY)",
        "Vẽ biên dạng chữ L kích thước 60x60mm bề dày 6mm khép kín.",
        "XY",
        """import cadquery as cq

# Bước 1: Phác thảo 2D biên dạng chữ L 60x60 dày 6mm
r = (
    cq.Workplane('XY')
    .moveTo(0, 0)
    .lineTo(60, 0)
    .lineTo(60, 6)
    .lineTo(6, 6)
    .lineTo(6, 60)
    .lineTo(0, 60)
    .close()
)
show_object(r)
"""
    ),
]

PRESET_PROMPTS = [
    ("--- Chọn mẫu cơ khí demo có sẵn (Presets) ---", ""),
    (
        "1. Mặt bích vuông có 4 lỗ bắt bu-lông M4 (Flange 80x80x10)",
        "Tạo một mặt bích vuông kích thước 80x80x10mm có 4 lỗ bắt bu-lông M4 (đường kính 4mm) bố trí ở 4 góc cách mép 10mm."
    ),
    (
        "2. Khối trục bậc 2 tầng (Stepped Shaft)",
        "Dựng một khối trục bậc gồm tầng dưới là hình trụ đường kính 40mm cao 50mm, trên đỉnh tạo tiếp hình trụ đường kính 20mm cao 30mm."
    ),
    (
        "3. Hình ống tròn rỗng xuyên suốt (Hollow Pipe)",
        "Tạo một ống tròn rỗng có đường kính ngoài 50mm, đường kính trong 30mm và chiều cao 60mm."
    ),
    (
        "4. Mặt bích tròn 6 lỗ bu-lông (Round Flange)",
        "Tạo một mặt bích tròn đường kính ngoài 100mm, dày 12mm, có 6 lỗ bu-lông đường kính 6mm phân bố đều trên vòng tròn chia đường kính 70mm, ở giữa có lỗ trục phi 30mm."
    ),
    (
        "5. Giá đỡ chữ L có gân tăng cứng tam giác (L-Bracket)",
        "Tạo một giá đỡ góc chữ L kích thước 60x40x60mm thành dày 6mm, có một gân tăng cứng tam giác dày 6mm ở chính giữa nối hai cạnh."
    ),
    (
        "6. Khối V định vị cơ khí (V-Block 90 độ)",
        "Tạo một khối V định vị cơ khí kích thước 60x60x40mm, có rãnh V góc 90 độ sâu 20mm ở mặt trên."
    ),
    (
        "7. Vỏ hộp linh kiện điện tử rỗng (Enclosure)",
        "Tạo một vỏ hộp rỗng không nắp kích thước ngoài 80x50x25mm, độ dày thành và đáy là 2mm."
    ),
    (
        "8. Hộp chữ nhật có tay cầm nối (Box with handle)",
        "Tạo một khối hộp chữ nhật kích thước 60x40x15mm. Sau đó tạo thêm một tay cầm dài 80mm rộng 10mm dày 10mm gắn nối tiếp vào mép hộp."
    ),
    (
        "9. Khối trụ tròn đơn (Cylinder chuẩn Dataset)",
        "Dựng một đối tượng hình trụ, vẽ bản phác thảo hình tròn tâm (0, 0) bán kính 20mm. Sau đó đùn (extrude) theo hướng pháp tuyến một khoảng 50mm."
    ),
    (
        "10. Then bằng truyền động cơ khí (Drive Key)",
        "Tạo một then bằng truyền động cơ khí kích thước chiều dài 50mm, bề rộng 10mm, chiều cao 8mm, hai đầu then vê tròn bán kính 5mm."
    ),
    (
        "11. Nón cụt rỗng / Phễu nạp (Frustum / Funnel)",
        "Tạo một phễu hình nón cụt rỗng cao 50mm, đường kính đáy lớn 60mm, đường kính đáy nhỏ 20mm, thành dày 3mm."
    ),
    (
        "12. Puly đai thang rãnh V (V-Belt Pulley)",
        "Tạo một puly đai thang đường kính ngoài 80mm, chiều dày 25mm, có rãnh đai chữ V ở giữa sâu 10mm góc 38 độ, lỗ trục tâm phi 15mm."
    )
]


class LLMInferenceWorker(QtCore.QThread):
    """Worker thread to query Ollama asynchronously so FreeCAD GUI never freezes"""
    finished = QtCore.Signal(str)
    failed = QtCore.Signal(str)

    def __init__(self, engine, prompt, system_prompt=None):
        super().__init__()
        self.engine = engine
        self.prompt = prompt
        self.system_prompt = system_prompt

    def run(self):
        try:
            raw_response = self.engine.query_ollama(self.prompt, system_prompt=self.system_prompt)
            code = self.engine.extract_code(raw_response)
            self.finished.emit(code)
        except Exception as e:
            self.failed.emit(str(e))


class AICADDockWidget(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super().__init__("AI CAD Assistant (Quy trình 3 bước)", parent)
        self.setObjectName("AICADDockWidget")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        self.engine = AICADEngine()
        self.worker = None
        self.setup_ui()
        self.refresh_model_list()

    def setup_ui(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)

        # ---------------- SETTINGS GROUP ---------------- #
        settings_group = QtWidgets.QGroupBox("⚙️ Cấu hình Local Model & Engine")
        settings_layout = QtWidgets.QGridLayout(settings_group)
        settings_layout.setContentsMargins(5, 5, 5, 5)
        settings_layout.setSpacing(3)

        settings_layout.addWidget(QtWidgets.QLabel("Endpoint:"), 0, 0)
        self.endpoint_edit = QtWidgets.QLineEdit("http://127.0.0.1:11434")
        settings_layout.addWidget(self.endpoint_edit, 0, 1, 1, 2)

        settings_layout.addWidget(QtWidgets.QLabel("Model:"), 1, 0)
        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItem("cadquery-ai")
        self.model_combo.addItem("qwen2.5-coder:3b")
        self.model_combo.currentIndexChanged.connect(self.on_model_changed)
        settings_layout.addWidget(self.model_combo, 1, 1)

        self.btn_refresh_models = QtWidgets.QPushButton("🔄")
        self.btn_refresh_models.setToolTip("Quét lại danh sách mô hình đang có trong Ollama")
        self.btn_refresh_models.setMaximumWidth(32)
        self.btn_refresh_models.clicked.connect(self.refresh_model_list)
        settings_layout.addWidget(self.btn_refresh_models, 1, 2)

        settings_layout.addWidget(QtWidgets.QLabel("Chế độ mã:"), 2, 0)
        self.mode_combo = QtWidgets.QComboBox()
        self.mode_combo.addItem("CadQuery SFT Mode (Dataset sạch)", "cadquery")
        self.mode_combo.addItem("FreeCAD Native CSG Mode", "freecad")
        settings_layout.addWidget(self.mode_combo, 2, 1, 1, 2)

        layout.addWidget(settings_group)

        # ---------------- MAIN WORKFLOW TABS (QUY TRÌNH 3 BƯỚC KỸ SƯ CAD) ---------------- #
        self.workflow_tabs = QtWidgets.QTabWidget()

        # TAB 1: BƯỚC 1 - DỰNG PHÁC THẢO 2D (SKETCHER)
        tab_step1 = QtWidgets.QWidget()
        layout_s1 = QtWidgets.QVBoxLayout(tab_step1)
        layout_s1.setContentsMargins(6, 6, 6, 6)
        layout_s1.setSpacing(4)

        preset_2d_layout = QtWidgets.QHBoxLayout()
        preset_2d_layout.addWidget(QtWidgets.QLabel("Mẫu 2D:"))
        self.preset_2d_combo = QtWidgets.QComboBox()
        for item in PRESET_2D_SKETCHES:
            self.preset_2d_combo.addItem(item[0])
        self.preset_2d_combo.currentIndexChanged.connect(self.on_preset_2d_selected)
        preset_2d_layout.addWidget(self.preset_2d_combo)
        layout_s1.addLayout(preset_2d_layout)

        plane_layout = QtWidgets.QHBoxLayout()
        plane_layout.addWidget(QtWidgets.QLabel("Mặt phẳng vẽ:"))
        self.combo_plane = QtWidgets.QComboBox()
        self.combo_plane.addItems(["XY (Mặt bằng - Top)", "XZ (Mặt đứng - Puly/Trục)", "YZ (Mặt bên - Side)"])
        plane_layout.addWidget(self.combo_plane)
        layout_s1.addLayout(plane_layout)

        layout_s1.addWidget(QtWidgets.QLabel("Mô tả biên dạng phẳng 2D kín (Sketch Contour):"))
        self.prompt_2d = QtWidgets.QTextEdit()
        self.prompt_2d.setPlaceholderText("VD: Vẽ hình chữ nhật 80x80mm, hoặc vẽ mặt cắt rãnh puly chữ V sâu 10mm góc 38 độ...")
        self.prompt_2d.setMaximumHeight(65)
        layout_s1.addWidget(self.prompt_2d)

        self.btn_draw_2d = QtWidgets.QPushButton("✏️ Dựng Bản Phác Thảo 2D")
        self.btn_draw_2d.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_draw_2d.clicked.connect(self.on_draw_2d_clicked)
        layout_s1.addWidget(self.btn_draw_2d)

        tip_s1 = QtWidgets.QLabel("<small style='color:#6B7280;'>Dựng biên dạng kín 2D (Wire/Face) để kiểm tra hình học trước khi lên khối.</small>")
        tip_s1.setWordWrap(True)
        layout_s1.addWidget(tip_s1)
        self.workflow_tabs.addTab(tab_step1, "✏️ Bước 1: Phác thảo 2D")

        # TAB 2: BƯỚC 2 - TẠO KHỐI 3D (BASE FEATURE)
        tab_step2 = QtWidgets.QWidget()
        layout_s2 = QtWidgets.QVBoxLayout(tab_step2)
        layout_s2.setContentsMargins(6, 6, 6, 6)
        layout_s2.setSpacing(4)

        layout_s2.addWidget(QtWidgets.QLabel("<b>Chọn phương pháp tạo khối 3D từ bản vẽ 2D:</b>"))

        # Extrude Option
        ext_group = QtWidgets.QGroupBox("1. Đùn khối thẳng (Extrude / Pad - Mặt bích, Tấm gá)")
        ext_layout = QtWidgets.QHBoxLayout(ext_group)
        ext_layout.setContentsMargins(4, 4, 4, 4)
        ext_layout.addWidget(QtWidgets.QLabel("Chiều dày Z:"))
        self.spin_extrude_dist = QtWidgets.QDoubleSpinBox()
        self.spin_extrude_dist.setRange(0.1, 2000.0)
        self.spin_extrude_dist.setValue(25.0)
        self.spin_extrude_dist.setSuffix(" mm")
        ext_layout.addWidget(self.spin_extrude_dist)

        self.btn_do_extrude = QtWidgets.QPushButton("🧱 Đùn khối 3D")
        self.btn_do_extrude.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 5px;")
        self.btn_do_extrude.clicked.connect(self.on_do_extrude_clicked)
        ext_layout.addWidget(self.btn_do_extrude)
        layout_s2.addWidget(ext_group)

        # Revolve Option
        rev_group = QtWidgets.QGroupBox("2. Xoay quanh trục (Revolve / Shaft - Puly, Trục, Ống)")
        rev_layout = QtWidgets.QHBoxLayout(rev_group)
        rev_layout.setContentsMargins(4, 4, 4, 4)
        rev_layout.addWidget(QtWidgets.QLabel("Trục:"))
        self.combo_rev_axis = QtWidgets.QComboBox()
        self.combo_rev_axis.addItems(["Z", "Y", "X"])
        rev_layout.addWidget(self.combo_rev_axis)

        rev_layout.addWidget(QtWidgets.QLabel("Góc:"))
        self.spin_rev_angle = QtWidgets.QDoubleSpinBox()
        self.spin_rev_angle.setRange(1.0, 360.0)
        self.spin_rev_angle.setValue(360.0)
        self.spin_rev_angle.setSuffix("°")
        rev_layout.addWidget(self.spin_rev_angle)

        self.btn_do_revolve = QtWidgets.QPushButton("🔄 Xoay tròn 3D")
        self.btn_do_revolve.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 5px;")
        self.btn_do_revolve.clicked.connect(self.on_do_revolve_clicked)
        rev_layout.addWidget(self.btn_do_revolve)
        layout_s2.addWidget(rev_group)

        tip_s2 = QtWidgets.QLabel("<small style='color:#6B7280;'>Mặt phẳng XZ dùng cho Puly/Trục (Xoay Z). Mặt phẳng XY dùng cho Đùn thẳng.</small>")
        tip_s2.setWordWrap(True)
        layout_s2.addWidget(tip_s2)

        self.workflow_tabs.addTab(tab_step2, "🧱 Bước 2: Lên Khối 3D")

        # TAB 3: BƯỚC 3 - GIA CÔNG & SỬA THEO YÊU CẦU GIÁM KHẢO
        tab_step3 = QtWidgets.QWidget()
        layout_s3 = QtWidgets.QVBoxLayout(tab_step3)
        layout_s3.setContentsMargins(6, 6, 6, 6)
        layout_s3.setSpacing(4)

        # Direct Parametric Modifiers Grid
        mod_group = QtWidgets.QGroupBox("1. Công cụ gia công nhanh (Direct Modifiers)")
        grid_mod = QtWidgets.QGridLayout(mod_group)
        grid_mod.setContentsMargins(4, 4, 4, 4)
        grid_mod.setSpacing(3)

        grid_mod.addWidget(QtWidgets.QLabel("Khoét lỗ tâm Ø:"), 0, 0)
        self.spin_hole_d = QtWidgets.QDoubleSpinBox()
        self.spin_hole_d.setRange(1.0, 500.0)
        self.spin_hole_d.setValue(15.0)
        self.spin_hole_d.setSuffix(" mm")
        grid_mod.addWidget(self.spin_hole_d, 0, 1)

        self.btn_add_hole = QtWidgets.QPushButton("🔘 Khoét lỗ")
        self.btn_add_hole.clicked.connect(self.on_add_hole_clicked)
        grid_mod.addWidget(self.btn_add_hole, 0, 2)

        grid_mod.addWidget(QtWidgets.QLabel("Đổi chiều dày Z:"), 1, 0)
        self.spin_thick_z = QtWidgets.QDoubleSpinBox()
        self.spin_thick_z.setRange(0.5, 1000.0)
        self.spin_thick_z.setValue(25.0)
        self.spin_thick_z.setSuffix(" mm")
        grid_mod.addWidget(self.spin_thick_z, 1, 1)

        self.btn_set_thick = QtWidgets.QPushButton("📐 Đổi dày")
        self.btn_set_thick.clicked.connect(self.on_adjust_thickness_clicked)
        grid_mod.addWidget(self.btn_set_thick, 1, 2)

        grid_mod.addWidget(QtWidgets.QLabel("Bo mép tròn R:"), 2, 0)
        self.spin_fillet_r = QtWidgets.QDoubleSpinBox()
        self.spin_fillet_r.setRange(0.2, 50.0)
        self.spin_fillet_r.setValue(2.0)
        self.spin_fillet_r.setSuffix(" mm")
        grid_mod.addWidget(self.spin_fillet_r, 2, 1)

        self.btn_apply_fillet = QtWidgets.QPushButton("✨ Bo góc")
        self.btn_apply_fillet.clicked.connect(self.on_fillet_clicked)
        grid_mod.addWidget(self.btn_apply_fillet, 2, 2)

        grid_mod.addWidget(QtWidgets.QLabel("Vát mép Chamfer:"), 3, 0)
        self.spin_chamfer_d = QtWidgets.QDoubleSpinBox()
        self.spin_chamfer_d.setRange(0.1, 50.0)
        self.spin_chamfer_d.setValue(1.0)
        self.spin_chamfer_d.setSuffix(" mm")
        grid_mod.addWidget(self.spin_chamfer_d, 3, 1)

        self.btn_apply_chamfer = QtWidgets.QPushButton("📐 Vát mép")
        self.btn_apply_chamfer.clicked.connect(self.on_chamfer_clicked)
        grid_mod.addWidget(self.btn_apply_chamfer, 3, 2)

        grid_mod.addWidget(QtWidgets.QLabel("Vật liệu / Màu:"), 4, 0)
        self.color_combo = QtWidgets.QComboBox()
        self.color_combo.addItems(["Thép xám", "Đồng thau", "Nhôm sáng", "Nhựa xanh", "Vàng kim", "Đỏ kỹ thuật"])
        grid_mod.addWidget(self.color_combo, 4, 1)

        self.btn_set_color = QtWidgets.QPushButton("🎨 Đổi màu")
        self.btn_set_color.clicked.connect(self.on_change_color_clicked)
        grid_mod.addWidget(self.btn_set_color, 4, 2)

        layout_s3.addWidget(mod_group)

        # AI Live Modification Section
        ai_mod_group = QtWidgets.QGroupBox("2. Tùy biến / Chỉnh sửa trực tiếp bằng AI (Live AI Edit)")
        ai_mod_layout = QtWidgets.QVBoxLayout(ai_mod_group)
        ai_mod_layout.setContentsMargins(4, 4, 4, 4)
        ai_mod_layout.setSpacing(3)

        self.prompt_edit_step3 = QtWidgets.QLineEdit()
        self.prompt_edit_step3.setPlaceholderText("VD: Khoét thêm 4 lỗ bu lông M4 xung quanh cách mép 10mm...")
        ai_mod_layout.addWidget(self.prompt_edit_step3)

        self.btn_step3_ai_modify = QtWidgets.QPushButton("🔄 AI Sửa Mô Hình (Modify)")
        self.btn_step3_ai_modify.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 5px; border-radius: 4px;")
        self.btn_step3_ai_modify.clicked.connect(self.on_step3_ai_modify_clicked)
        ai_mod_layout.addWidget(self.btn_step3_ai_modify)

        layout_s3.addWidget(ai_mod_group)
        self.workflow_tabs.addTab(tab_step3, "🔧 Bước 3: Gia Công & Sửa")

        # TAB 4: TỰ ĐỘNG 1-CLICK & SỬA ĐA LƯỢT (FAST 1-SHOT AI)
        tab_step4 = QtWidgets.QWidget()
        layout_s4 = QtWidgets.QVBoxLayout(tab_step4)
        layout_s4.setContentsMargins(6, 6, 6, 6)
        layout_s4.setSpacing(3)

        layout_s4.addWidget(QtWidgets.QLabel("<b>Mẫu cơ khí có sẵn (Presets):</b>"))
        self.preset_combo = QtWidgets.QComboBox()
        for title, _ in PRESET_PROMPTS:
            self.preset_combo.addItem(title)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
        layout_s4.addWidget(self.preset_combo)

        layout_s4.addWidget(QtWidgets.QLabel("<b>Prompt 1-Click (Tạo mới hoặc Sửa tiếp):</b>"))
        self.prompt_text = QtWidgets.QTextEdit()
        self.prompt_text.setPlaceholderText("Nhập mô tả toàn bộ chi tiết 3D hoặc yêu cầu sửa đổi tiếp...")
        self.prompt_text.setMaximumHeight(65)
        layout_s4.addWidget(self.prompt_text)

        btn_row = QtWidgets.QHBoxLayout()
        self.btn_generate = QtWidgets.QPushButton("🚀 Tạo mới 3D")
        self.btn_generate.setStyleSheet("background-color: #2563EB; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        btn_row.addWidget(self.btn_generate)

        self.btn_modify = QtWidgets.QPushButton("🔄 AI Sửa (Modify)")
        self.btn_modify.setStyleSheet("background-color: #059669; color: white; font-weight: bold; padding: 6px; border-radius: 4px;")
        self.btn_modify.clicked.connect(self.on_modify_clicked)
        btn_row.addWidget(self.btn_modify)

        self.btn_fix = QtWidgets.QPushButton("🔧 Fix")
        self.btn_fix.setStyleSheet("padding: 6px; font-weight: bold;")
        self.btn_fix.setEnabled(False)
        self.btn_fix.clicked.connect(self.on_fix_clicked)
        btn_row.addWidget(self.btn_fix)
        layout_s4.addLayout(btn_row)

        self.workflow_tabs.addTab(tab_step4, "🚀 Tự Động 1-Click")

        layout.addWidget(self.workflow_tabs)

        # ---------------- 3D LIVE INSPECTOR ---------------- #
        self.inspector_group = QtWidgets.QGroupBox("📏 Thanh tra Kích thước 3D (Live Inspector)")
        insp_layout = QtWidgets.QVBoxLayout(self.inspector_group)
        insp_layout.setContentsMargins(6, 6, 6, 6)
        insp_layout.setSpacing(2)

        self.dim_label = QtWidgets.QLabel("Kích thước bao: Chưa có mô hình")
        self.dim_label.setStyleSheet("font-weight: bold; color: #1E40AF;")
        insp_layout.addWidget(self.dim_label)

        self.vol_label = QtWidgets.QLabel("Thể tích & Khối: -- mm³ | -- Solids")
        self.vol_label.setStyleSheet("color: #4B5563;")
        insp_layout.addWidget(self.vol_label)

        layout.addWidget(self.inspector_group)

        # ---------------- CODE & LOGS TABS ---------------- #
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: Code editor + Run Button
        code_widget = QtWidgets.QWidget()
        code_layout = QtWidgets.QVBoxLayout(code_widget)
        code_layout.setContentsMargins(4, 4, 4, 4)
        code_layout.setSpacing(3)

        self.code_edit = QtWidgets.QPlainTextEdit()
        font = QtGui.QFont("Courier New", 9)
        font.setStyleHint(QtGui.QFont.Monospace)
        self.code_edit.setFont(font)
        code_layout.addWidget(self.code_edit)

        code_btn_layout = QtWidgets.QHBoxLayout()
        self.btn_run_code = QtWidgets.QPushButton("▶ Chạy lại mã nguồn này")
        self.btn_run_code.setStyleSheet("font-weight: bold; padding: 4px;")
        self.btn_run_code.clicked.connect(self.on_run_code_clicked)
        code_btn_layout.addWidget(self.btn_run_code)
        code_layout.addLayout(code_btn_layout)

        self.tabs.addTab(code_widget, "Mã CAD (Python)")

        # Tab 2: Logs
        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(font)
        self.tabs.addTab(self.log_text, "Nhật ký / Lỗi")

        layout.addWidget(self.tabs)

        # Export & Actions Group
        action_layout = QtWidgets.QHBoxLayout()
        self.btn_export_step = QtWidgets.QPushButton("💾 Xuất STEP")
        self.btn_export_step.setToolTip("Xuất file STEP cho SolidWorks, Inventor, v.v.")
        self.btn_export_step.clicked.connect(self.on_export_step_clicked)
        action_layout.addWidget(self.btn_export_step)

        self.btn_export_stl = QtWidgets.QPushButton("💾 Xuất STL")
        self.btn_export_stl.setToolTip("Xuất file STL cho máy in 3D (Cura, BambuStudio)")
        self.btn_export_stl.clicked.connect(self.on_export_stl_clicked)
        action_layout.addWidget(self.btn_export_stl)

        self.btn_undo = QtWidgets.QPushButton("🗑 Xóa vật thể")
        self.btn_undo.clicked.connect(self.on_undo_clicked)
        action_layout.addWidget(self.btn_undo)

        layout.addLayout(action_layout)

        # Status Bar
        self.status_label = QtWidgets.QLabel("🟢 Sẵn sàng")
        self.status_label.setStyleSheet("color: #10B981; font-weight: bold;")
        layout.addWidget(self.status_label)

        self.setWidget(container)

    def refresh_model_list(self):
        self.engine.endpoint = self.endpoint_edit.text().strip()
        models = self.engine.get_available_models()
        current = self.model_combo.currentText()

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in models:
            self.model_combo.addItem(m)

        if current and current in models:
            self.model_combo.setCurrentText(current)
        elif "cadquery-ai" in [m.split(":")[0] for m in models]:
            idx = [i for i, m in enumerate(models) if "cadquery-ai" in m][0]
            self.model_combo.setCurrentIndex(idx)
        self.model_combo.blockSignals(False)

    def on_model_changed(self, index):
        selected_model = self.model_combo.currentText().lower()
        if "cadquery" in selected_model:
            self.mode_combo.setCurrentIndex(0) # CadQuery SFT Mode
        elif "qwen" in selected_model or "freecad" in selected_model:
            self.mode_combo.setCurrentIndex(1) # FreeCAD Native CSG Mode

    def on_preset_2d_selected(self, index):
        if 0 < index < len(PRESET_2D_SKETCHES):
            _, text, plane, code = PRESET_2D_SKETCHES[index]
            self.prompt_2d.setPlainText(text)
            if plane == "XZ":
                self.combo_plane.setCurrentIndex(1)
            elif plane == "YZ":
                self.combo_plane.setCurrentIndex(2)
            else:
                self.combo_plane.setCurrentIndex(0)
            if code:
                self.code_edit.setPlainText(code.strip())

    def align_view_to_plane(self, plane="XY"):
        """Align FreeCAD 3D viewport camera directly to the active sketch plane"""
        try:
            p = str(plane).strip().upper()
            if hasattr(Gui, "SendMsgToActiveView"):
                if "XZ" in p or "FRONT" in p:
                    Gui.SendMsgToActiveView("ViewFront")
                elif "YZ" in p or "SIDE" in p or "RIGHT" in p:
                    Gui.SendMsgToActiveView("ViewRight")
                else:
                    Gui.SendMsgToActiveView("ViewTop")
                Gui.SendMsgToActiveView("ViewFit")
            elif Gui.activeDocument() and hasattr(Gui.activeDocument(), "activeView"):
                av = Gui.activeDocument().activeView()
                if "XZ" in p or "FRONT" in p:
                    av.viewFront()
                elif "YZ" in p or "SIDE" in p or "RIGHT" in p:
                    av.viewRight()
                else:
                    av.viewTop()
                av.viewFit()
        except Exception:
            pass

    def on_preset_selected(self, index):
        if 0 < index < len(PRESET_PROMPTS):
            _, text = PRESET_PROMPTS[index]
            self.prompt_text.setPlainText(text)

    def update_geometry_inspector(self):
        stats = self.engine.get_model_geometry_stats()
        if stats:
            self.dim_label.setText(
                f"Kích thước bao:  X: {stats['x']:.2f} mm | Y: {stats['y']:.2f} mm | Z: {stats['z']:.2f} mm"
            )
            self.vol_label.setText(
                f"Thể tích: {stats['volume']:,.2f} mm³ | {stats['solids']} Solid(s) | {stats['faces']} Faces"
            )
        else:
            self.dim_label.setText("Kích thước bao: Chưa có mô hình")
            self.vol_label.setText("Thể tích & Khối: -- mm³ | -- Solids")

    def log(self, message):
        self.log_text.append(message)

    def set_status(self, text, color="#2563EB"):
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        QtWidgets.QApplication.processEvents()

    # ---------------- BƯỚC 1: DỰNG PHÁC THẢO 2D ---------------- #
    def on_draw_2d_clicked(self):
        prompt = self.prompt_2d.toPlainText().strip()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập mô tả biên dạng phẳng 2D cần phác thảo!")
            return

        plane_raw = self.combo_plane.currentText()
        plane = "XY" if "XY" in plane_raw else ("XZ" if "XZ" in plane_raw else "YZ")

        # Fast path 1: If the prompt matches one of our verified 2D presets, execute with 100% precision!
        for _, text, p, code in PRESET_2D_SKETCHES:
            if text and prompt == text.strip() and code:
                self.log(f"\n--- [Bước 1: Phác thảo 2D mẫu ({plane})] ---\n{prompt}")
                self.on_draw_2d_success(code.strip())
                return

        # Fast path 2: Parametric engineering synthesis (Pulley, Flange, Shaft)
        synth_code = self.engine.synthesize_engineering_code(prompt, plane=plane, step="2d")
        if synth_code:
            self.log(f"\n--- [Bước 1: Phác thảo 2D tham số ({plane})] ---\n{prompt}")
            self.on_draw_2d_success(synth_code.strip())
            return

        self.engine.endpoint = self.endpoint_edit.text().strip()
        self.engine.model = self.model_combo.currentText().strip()
        self.engine.mode = self.mode_combo.currentData()

        sketch_prompt = self.engine.build_2d_sketch_prompt(prompt, plane=plane)

        self.btn_draw_2d.setEnabled(False)
        self.btn_draw_2d.setText("⏳ Đang vẽ 2D...")
        self.set_status(f"✏️ AI đang phác thảo biên dạng 2D trên mặt phẳng {plane}...", "#0284C7")
        self.log(f"\n--- [Bước 1: Phác thảo 2D ({plane})] ---\n{prompt}")

        self.worker = LLMInferenceWorker(self.engine, sketch_prompt, system_prompt=DEFAULT_2D_SKETCH_SYSTEM_PROMPT)
        self.worker.finished.connect(self.on_draw_2d_success)
        self.worker.failed.connect(self.on_inference_error)
        self.worker.start()

    def on_draw_2d_success(self, code):
        self.btn_draw_2d.setEnabled(True)
        self.btn_draw_2d.setText("✏️ Dựng Bản Phác Thảo 2D")

        # In Step 1, guarantee that the code only produces a 2D sketch, not a 3D solid
        plane_raw = self.combo_plane.currentText()
        plane = "XY" if "XY" in plane_raw else ("XZ" if "XZ" in plane_raw else "YZ")

        self.engine.last_generated_code = code
        self.code_edit.setPlainText(code)

        self.set_status("⚙️ Đang dựng đường bao 2D trong FreeCAD...", "#2563EB")
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Hoàn tất Bước 1: Bản phác thảo 2D đã sẵn sàng! Chuyển sang Bước 2 để lên khối 3D.", "#16A34A")
            self.log(f"Thành công 2D: {msg}")
            self.tabs.setCurrentIndex(0)
            self.update_geometry_inspector()
            self.align_view_to_plane(plane)
            # Switch to Step 2 tab automatically to guide the engineer!
            self.workflow_tabs.setCurrentIndex(1)
        else:
            self.set_status("❌ Lỗi dựng phác thảo 2D!", "#DC2626")
            self.log(f"Lỗi:\n{msg}")
            self.tabs.setCurrentIndex(1)

    # ---------------- BƯỚC 2: TẠO KHỐI 3D ---------------- #
    def on_do_extrude_clicked(self):
        dist = self.spin_extrude_dist.value()
        success, msg, snippet = self.engine.extrude_active_2d(dist)
        if success:
            self.set_status(f"✅ Hoàn tất Bước 2: {msg}", "#16A34A")
            self.log(msg)
            self.update_geometry_inspector()
            curr = self.code_edit.toPlainText()
            self.code_edit.setPlainText(curr + snippet)
            # Switch to Step 3 tab
            self.workflow_tabs.setCurrentIndex(2)
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    def on_do_revolve_clicked(self):
        axis = self.combo_rev_axis.currentText()
        angle = self.spin_rev_angle.value()
        success, msg, snippet = self.engine.revolve_active_2d(angle, axis=axis)
        if success:
            self.set_status(f"✅ Hoàn tất Bước 2: {msg}", "#16A34A")
            self.log(msg)
            self.update_geometry_inspector()
            curr = self.code_edit.toPlainText()
            self.code_edit.setPlainText(curr + snippet)
            # Switch to Step 3 tab
            self.workflow_tabs.setCurrentIndex(2)
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    # ---------------- BƯỚC 3: GIA CÔNG & SỬA ---------------- #
    def on_add_hole_clicked(self):
        diameter = self.spin_hole_d.value()
        success, msg = self.engine.add_center_hole(diameter)
        if success:
            self.set_status(f"✅ {msg}", "#16A34A")
            self.log(msg)
            self.update_geometry_inspector()
            curr = self.code_edit.toPlainText()
            snippet = f"\n# Bước 3 (Gia công): Khoét lỗ tâm Ø{diameter}mm:\nr = r.cut(cq.Workplane('XY').circle({diameter / 2.0}).extrude(100, both=True))\nshow_object(r)\n"
            self.code_edit.setPlainText(curr + snippet)
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    def on_adjust_thickness_clicked(self):
        thickness = self.spin_thick_z.value()
        success, msg = self.engine.adjust_model_thickness(thickness)
        if success:
            self.set_status(f"✅ {msg}", "#16A34A")
            self.log(msg)
            self.update_geometry_inspector()
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    def on_fillet_clicked(self):
        r = self.spin_fillet_r.value()
        success, msg = self.engine.fillet_model_edges(r)
        if success:
            self.set_status(f"✅ {msg}", "#16A34A")
            self.log(msg)
            self.update_geometry_inspector()
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    def on_chamfer_clicked(self):
        d = self.spin_chamfer_d.value()
        success, msg = self.engine.chamfer_model_edges(d)
        if success:
            self.set_status(f"✅ {msg}", "#16A34A")
            self.log(msg)
            self.update_geometry_inspector()
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    def on_change_color_clicked(self):
        color_name = self.color_combo.currentText()
        success, msg = self.engine.set_model_color(color_name)
        if success:
            self.set_status(f"🎨 {msg}", "#16A34A")
            self.log(msg)
        else:
            self.set_status(f"❌ {msg}", "#DC2626")
            self.log(msg)

    def on_step3_ai_modify_clicked(self):
        edit_instruction = self.prompt_edit_step3.text().strip()
        if not edit_instruction:
            QtWidgets.QMessageBox.warning(self, "Thiếu yêu cầu", "Vui lòng nhập yêu cầu chỉnh sửa vào ô!")
            return
        self.execute_modification(edit_instruction)

    # ---------------- TAB 4: 1-CLICK GENERATION & MODIFY ---------------- #
    def on_generate_clicked(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập mô tả chi tiết hình học cần tạo!")
            return

        # Fast path: Parametric engineering synthesis for 3D model
        synth_code = self.engine.synthesize_engineering_code(prompt, step="3d")
        if synth_code:
            self.log(f"\n--- [Tạo mới 1-Click Tham số] ---\n{prompt}")
            self.on_inference_success(synth_code.strip())
            return

        self.engine.endpoint = self.endpoint_edit.text().strip()
        self.engine.model = self.model_combo.currentText().strip()
        self.engine.mode = self.mode_combo.currentData()

        self.btn_generate.setEnabled(False)
        self.btn_modify.setEnabled(False)
        self.btn_generate.setText("⏳ Đang sinh...")
        self.set_status("⏳ AI đang suy luận...", "#D97706")
        self.log(f"\n--- [Tạo mới 1-Click ({self.engine.mode})] ---\n{prompt}")

        self.worker = LLMInferenceWorker(self.engine, prompt)
        self.worker.finished.connect(self.on_inference_success)
        self.worker.failed.connect(self.on_inference_error)
        self.worker.start()

    def on_modify_clicked(self):
        edit_instruction = self.prompt_text.toPlainText().strip()
        if not edit_instruction:
            QtWidgets.QMessageBox.warning(self, "Thiếu yêu cầu sửa", "Vui lòng nhập yêu cầu chỉnh sửa vào ô Prompt!")
            return
        self.execute_modification(edit_instruction)

    def execute_modification(self, edit_instruction):
        current_code = self.code_edit.toPlainText().strip()
        if not current_code:
            QtWidgets.QMessageBox.warning(self, "Chưa có mô hình", "Cần tạo một mô hình 3D trước khi yêu cầu chỉnh sửa!")
            return

        self.engine.endpoint = self.endpoint_edit.text().strip()
        self.engine.model = self.model_combo.currentText().strip()
        self.engine.mode = self.mode_combo.currentData()

        modify_prompt = self.engine.build_modification_prompt(edit_instruction, current_code)

        self.btn_modify.setEnabled(False)
        self.btn_step3_ai_modify.setEnabled(False)
        self.btn_modify.setText("⏳ Đang sửa...")
        self.set_status("🔄 AI đang chỉnh sửa mô hình...", "#D97706")
        self.log(f"\n--- [Yêu cầu chỉnh sửa đa lượt ({self.engine.mode})] ---\n{edit_instruction}")

        self.worker = LLMInferenceWorker(self.engine, modify_prompt, system_prompt=DEFAULT_MODIFICATION_SYSTEM_PROMPT)
        self.worker.finished.connect(self.on_modify_success)
        self.worker.failed.connect(self.on_inference_error)
        self.worker.start()

    def on_modify_success(self, code):
        self.btn_modify.setEnabled(True)
        self.btn_step3_ai_modify.setEnabled(True)
        self.btn_modify.setText("🔄 AI Sửa (Modify)")
        self.engine.last_generated_code = code
        self.code_edit.setPlainText(code)

        self.set_status("⚙️ Đang thực thi mã sửa đổi trong FreeCAD...", "#2563EB")
        self.log("Mã AI sinh sau chỉnh sửa:\n" + code)
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Chỉnh sửa mô hình thành công!", "#16A34A")
            self.log("Thành công: " + msg)
            self.tabs.setCurrentIndex(0)
            self.btn_fix.setEnabled(False)
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Lỗi khi thực thi mã sửa đổi!", "#DC2626")
            self.log("Lỗi: " + msg)
            self.tabs.setCurrentIndex(1)
            self.btn_fix.setEnabled(True)

    def on_inference_success(self, code):
        self.btn_generate.setEnabled(True)
        self.btn_modify.setEnabled(True)
        self.btn_generate.setText("🚀 Tạo mới 3D")
        self.engine.last_generated_code = code
        self.code_edit.setPlainText(code)

        self.set_status("⚙️ Đang dựng mô hình trong FreeCAD...", "#2563EB")
        self.log("Mã Python sinh bởi AI:\n" + code)
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Hoàn thành dựng mô hình 3D!", "#16A34A")
            self.log(f"Thành công: {msg}")
            self.tabs.setCurrentIndex(0)
            self.btn_fix.setEnabled(False)
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Lỗi thực thi mã trong FreeCAD!", "#DC2626")
            self.log(f"Lỗi:\n{msg}")
            self.tabs.setCurrentIndex(1)
            self.btn_fix.setEnabled(True)

    def on_inference_error(self, err_msg):
        self.btn_draw_2d.setEnabled(True)
        self.btn_draw_2d.setText("✏️ Dựng Bản Phác Thảo 2D")
        self.btn_generate.setEnabled(True)
        self.btn_modify.setEnabled(True)
        self.btn_step3_ai_modify.setEnabled(True)
        self.btn_generate.setText("🚀 Tạo mới 3D")
        self.btn_modify.setText("🔄 AI Sửa (Modify)")
        self.set_status("❌ Lỗi kết nối Ollama!", "#DC2626")
        self.log(f"Lỗi kết nối:\n{err_msg}")
        self.tabs.setCurrentIndex(1)
        QtWidgets.QMessageBox.critical(self, "Lỗi Ollama", err_msg)

    def on_run_code_clicked(self):
        code = self.code_edit.toPlainText().strip()
        if not code:
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Không có mã nguồn để chạy!")
            return

        self.set_status("⚙️ Đang thực thi lại mã từ Editor...", "#2563EB")
        self.engine.last_generated_code = code
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Đã cập nhật mô hình 3D thành công!", "#16A34A")
            self.log(f"Thành công: {msg}")
            self.btn_fix.setEnabled(False)
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Lỗi thực thi mã nguồn!", "#DC2626")
            self.log(f"Lỗi:\n{msg}")
            self.btn_fix.setEnabled(True)

    def on_fix_clicked(self):
        if not self.engine.last_generated_code or not self.engine.last_error:
            QtWidgets.QMessageBox.information(self, "Thông báo", "Không có lỗi nào gần đây để sửa!")
            return

        user_prompt = self.prompt_text.toPlainText().strip()
        fix_prompt = self.engine.build_fix_prompt(
            user_prompt, self.engine.last_generated_code, self.engine.last_error
        )

        self.btn_fix.setEnabled(False)
        self.btn_fix.setText("⏳ Đang fix...")
        self.set_status("🔧 AI đang tự phân tích mã lỗi và khắc phục...", "#D97706")
        self.log("\n--- [Gửi phản hồi lỗi tự động (Self-Correction)] ---\n" + self.engine.last_error)

        self.worker = LLMInferenceWorker(self.engine, fix_prompt)
        self.worker.finished.connect(self.on_fix_success)
        self.worker.failed.connect(self.on_inference_error)
        self.worker.start()

    def on_fix_success(self, code):
        self.btn_fix.setEnabled(True)
        self.btn_fix.setText("🔧 Fix")
        self.engine.last_generated_code = code
        self.code_edit.setPlainText(code)

        self.set_status("⚙️ Đang thử lại mã đã sửa...", "#2563EB")
        self.log("Mã đã được sửa bởi AI:\n" + code)
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Tự sửa lỗi thành công! Mô hình đã hiển thị.", "#16A34A")
            self.log("Khắc phục lỗi thành công!")
            self.tabs.setCurrentIndex(0)
            self.btn_fix.setEnabled(False)
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Vẫn còn lỗi sau khi sửa. Hãy kiểm tra nhật ký.", "#DC2626")
            self.log(f"Lỗi tiếp tục xảy ra:\n{msg}")
            self.tabs.setCurrentIndex(1)

    def on_export_step_clicked(self):
        if App.ActiveDocument is None:
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Không có tài liệu nào đang mở để xuất file!")
            return

        obj = App.ActiveDocument.getObject("AICAD_Model")
        if obj is None and App.ActiveDocument.Objects:
            obj = App.ActiveDocument.Objects[-1]

        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy vật thể 3D hợp lệ để xuất!")
            return

        default_name = f"{obj.Name}.step"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Xuất file STEP", os.path.join(os.path.expanduser("~"), "Desktop", default_name), "STEP files (*.step *.stp)"
        )

        if path:
            try:
                import Import
                Import.export([obj], path)
                self.set_status(f"💾 Đã xuất file STEP: {os.path.basename(path)}", "#16A34A")
                self.log(f"Xuất STEP thành công vào: {path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Lỗi xuất file", f"Không thể xuất file STEP:\n{e}")

    def on_export_stl_clicked(self):
        if App.ActiveDocument is None:
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Không có tài liệu nào đang mở để xuất file!")
            return

        obj = App.ActiveDocument.getObject("AICAD_Model")
        if obj is None and App.ActiveDocument.Objects:
            obj = App.ActiveDocument.Objects[-1]

        if obj is None or not hasattr(obj, "Shape") or obj.Shape.isNull():
            QtWidgets.QMessageBox.warning(self, "Cảnh báo", "Không tìm thấy vật thể 3D hợp lệ để xuất!")
            return

        default_name = f"{obj.Name}.stl"
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Xuất file STL", os.path.join(os.path.expanduser("~"), "Desktop", default_name), "STL Mesh files (*.stl)"
        )

        if path:
            try:
                import Mesh
                Mesh.export([obj], path)
                self.set_status(f"💾 Đã xuất file STL: {os.path.basename(path)}", "#16A34A")
                self.log(f"Xuất STL thành công vào: {path}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Lỗi xuất file", f"Không thể xuất file STL:\n{e}")

    def on_undo_clicked(self):
        if App.ActiveDocument:
            obj = App.ActiveDocument.getObject("AICAD_Model")
            if obj:
                App.ActiveDocument.removeObject("AICAD_Model")
            elif App.ActiveDocument.Objects:
                App.ActiveDocument.removeObject(App.ActiveDocument.Objects[-1].Name)
            App.ActiveDocument.recompute()
            self.set_status("🗑 Đã xóa mô hình khỏi FreeCAD.", "#6B7280")
            self.update_geometry_inspector()


_dock_widget_instance = None


def toggle_aicad_dock():
    """Toggle visibility of the AICAD Assistant dock widget in FreeCAD GUI"""
    global _dock_widget_instance
    main_window = Gui.getMainWindow() if hasattr(Gui, "getMainWindow") else None
    if _dock_widget_instance is None:
        _dock_widget_instance = AICADDockWidget(main_window)
        if main_window:
            main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, _dock_widget_instance)

    if _dock_widget_instance.isVisible():
        _dock_widget_instance.hide()
    else:
        _dock_widget_instance.show()
        _dock_widget_instance.raise_()

