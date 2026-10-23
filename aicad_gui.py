# SPDX-License-Identifier: LGPL-2.1-or-later
"""
AICAD GUI: Comprehensive AI CAD Assistant for FreeCAD.
Features:
- Dual-Engine Support (CadQuery SFT / FreeCAD Native CSG)
- Auto-Model Discovery from Ollama (/api/tags)
- Real-time 3D Geometry & Dimension Inspector (Bounding Box, Volume, Solids)
- 1-Click Quick Post-Processing (Extrude 2D->3D, Scale x10/x1000)
- 12 Production-Ready Mechanical Presets
- Asynchronous Non-blocking Inference (QThread)
- Live Code Editor with 1-click Re-run
- Direct STEP & STL Export
"""

import os
import FreeCAD as App
import FreeCADGui as Gui
from PySide import QtCore, QtWidgets, QtGui

from aicad_engine import AICADEngine

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

    def __init__(self, engine, prompt):
        super().__init__()
        self.engine = engine
        self.prompt = prompt

    def run(self):
        try:
            raw_response = self.engine.query_ollama(self.prompt)
            code = self.engine.extract_code(raw_response)
            self.finished.emit(code)
        except Exception as e:
            self.failed.emit(str(e))


class AICADDockWidget(QtWidgets.QDockWidget):
    def __init__(self, parent=None):
        super().__init__("AI Text-to-CAD Assistant", parent)
        self.setObjectName("AICADDockWidget")
        self.setAllowedAreas(QtCore.Qt.LeftDockWidgetArea | QtCore.Qt.RightDockWidgetArea)

        self.engine = AICADEngine()
        self.worker = None
        self.setup_ui()
        self.refresh_model_list()

    def setup_ui(self):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header Banner
        header_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel("<b>⚡ AI Text-to-CAD</b> <span style='color:#10B981;'>(Dual Engine)</span>")
        title_label.setStyleSheet("font-size: 11pt; color: #1E40AF;")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        layout.addLayout(header_layout)

        # Settings Group (Endpoint, Model, Engine Mode)
        settings_group = QtWidgets.QGroupBox("⚙️ Cấu hình Local Model & Engine")
        settings_layout = QtWidgets.QGridLayout(settings_group)
        settings_layout.setContentsMargins(6, 6, 6, 6)
        settings_layout.setSpacing(4)

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

        # Preset Dropdown for Fast Live Demo
        layout.addWidget(QtWidgets.QLabel("<b>🎯 Mẫu cơ khí mẫu (Presets):</b>"))
        self.preset_combo = QtWidgets.QComboBox()
        for title, _ in PRESET_PROMPTS:
            self.preset_combo.addItem(title)
        self.preset_combo.currentIndexChanged.connect(self.on_preset_selected)
        layout.addWidget(self.preset_combo)

        # Prompt Input
        layout.addWidget(QtWidgets.QLabel("<b>Mô tả hình học (Prompt):</b> <small style='color:#6B7280;'>(Ctrl+Enter để chạy)</small>"))
        self.prompt_text = QtWidgets.QTextEdit()
        self.prompt_text.setPlaceholderText(
            "Nhập mô tả chi tiết hình học cần tạo (Ví dụ: Tạo một mặt bích vuông kích thước 80x80x10mm có 4 lỗ bắt bu-lông M4)..."
        )
        self.prompt_text.setMaximumHeight(85)
        layout.addWidget(self.prompt_text)

        # Shortcut Ctrl+Enter for generation
        QShortcutClass = getattr(QtGui, "QShortcut", getattr(QtWidgets, "QShortcut", None))
        if QShortcutClass:
            self.shortcut = QShortcutClass(QtGui.QKeySequence("Ctrl+Return"), self.prompt_text)
            self.shortcut.activated.connect(self.on_generate_clicked)

        # Primary Action Buttons
        btn_layout = QtWidgets.QHBoxLayout()
        self.btn_generate = QtWidgets.QPushButton("🚀 Tạo mô hình 3D")
        self.btn_generate.setStyleSheet(
            "background-color: #2563EB; color: white; font-weight: bold; padding: 7px; border-radius: 4px;"
        )
        self.btn_generate.clicked.connect(self.on_generate_clicked)
        btn_layout.addWidget(self.btn_generate)

        self.btn_fix = QtWidgets.QPushButton("🔧 Tự sửa lỗi (Fix)")
        self.btn_fix.setStyleSheet("padding: 7px; border-radius: 4px; font-weight: bold;")
        self.btn_fix.setEnabled(False)
        self.btn_fix.clicked.connect(self.on_fix_clicked)
        btn_layout.addWidget(self.btn_fix)

        layout.addLayout(btn_layout)

        # 3D Geometry & Dimension Inspector Card
        self.inspector_group = QtWidgets.QGroupBox("📏 Thanh tra Kích thước 3D (Live Inspector)")
        insp_layout = QtWidgets.QVBoxLayout(self.inspector_group)
        insp_layout.setContentsMargins(6, 6, 6, 6)
        insp_layout.setSpacing(2)

        self.dim_label = QtWidgets.QLabel("Kích thước bao (Bounding Box): Chưa có mô hình")
        self.dim_label.setStyleSheet("font-weight: bold; color: #1E40AF;")
        insp_layout.addWidget(self.dim_label)

        self.vol_label = QtWidgets.QLabel("Thể tích & Khối: -- mm³ | -- Solids")
        self.vol_label.setStyleSheet("color: #4B5563;")
        insp_layout.addWidget(self.vol_label)

        layout.addWidget(self.inspector_group)

        # Tabs for Generated Code & Execution Log
        self.tabs = QtWidgets.QTabWidget()

        # Tab 1: Code editor + Run Button
        code_widget = QtWidgets.QWidget()
        code_layout = QtWidgets.QVBoxLayout(code_widget)
        code_layout.setContentsMargins(4, 4, 4, 4)
        code_layout.setSpacing(4)

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

        self.btn_extrude_face = QtWidgets.QPushButton("⬆ Đùn dày (10mm)")
        self.btn_extrude_face.setToolTip("Nếu chi tiết đang là mặt phẳng 2D, bấm để đùn thành khối 3D dày 10mm")
        self.btn_extrude_face.clicked.connect(self.on_extrude_face_clicked)
        code_btn_layout.addWidget(self.btn_extrude_face)

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
        self.status_label = QtWidgets.QLabel("🟢 Sẵn sàng (Dual Engine CadQuery + FreeCAD)")
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

    def on_generate_clicked(self):
        prompt = self.prompt_text.toPlainText().strip()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập mô tả chi tiết hình học cần tạo!")
            return

        self.engine.endpoint = self.endpoint_edit.text().strip()
        self.engine.model = self.model_combo.currentText().strip()
        self.engine.mode = self.mode_combo.currentData()

        self.btn_generate.setEnabled(False)
        self.btn_generate.setText("⏳ Đang sinh mã...")
        self.set_status("⏳ AI đang suy luận trên GPU RTX 3050...", "#D97706")
        self.log(f"\n--- [Prompt Mới ({self.engine.mode})] ---\n{prompt}")

        self.worker = LLMInferenceWorker(self.engine, prompt)
        self.worker.finished.connect(self.on_inference_success)
        self.worker.failed.connect(self.on_inference_error)
        self.worker.start()

    def on_inference_success(self, code):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("🚀 Tạo mô hình 3D")
        self.engine.last_generated_code = code
        self.code_edit.setPlainText(code)

        self.set_status("⚙️ Đang thực thi mã dựng hình trong FreeCAD...", "#2563EB")
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Hoàn tất! Mô hình 3D đã được tạo.", "#16A34A")
            self.log(f"Thành công: {msg}")
            self.btn_fix.setEnabled(False)
            self.tabs.setCurrentIndex(0)
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Lỗi thực thi! Nhấn 'Tự sửa lỗi (Fix)' để AI sửa lại.", "#DC2626")
            self.log(f"Lỗi:\n{msg}")
            self.tabs.setCurrentIndex(1)
            self.btn_fix.setEnabled(True)

    def on_run_code_clicked(self):
        code = self.code_edit.toPlainText().strip()
        if not code:
            return
        self.set_status("⚙️ Đang chạy lại mã nguồn tùy chỉnh...", "#2563EB")
        success, msg = self.engine.execute_code(code)
        if success:
            self.set_status("✅ Cập nhật mô hình 3D thành công!", "#16A34A")
            self.log("Thực thi mã thành công.")
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Lỗi thực thi mã!", "#DC2626")
            self.log(f"Lỗi:\n{msg}")
            self.tabs.setCurrentIndex(1)

    def on_extrude_face_clicked(self):
        doc = App.ActiveDocument
        if not doc or not doc.Objects:
            return
        obj = doc.getObject("AICAD_Model") or doc.Objects[-1]
        if hasattr(obj, "Shape") and len(getattr(obj.Shape, "Solids", [])) == 0:
            try:
                import Part
                solid = obj.Shape.extrude(App.Vector(0, 0, 10))
                obj.Shape = solid
                doc.recompute()
                self.set_status("✅ Đã đùn dày chi tiết thêm 10mm!", "#16A34A")
                self.update_geometry_inspector()
            except Exception as e:
                self.log(f"Lỗi đùn mặt: {e}")

    def on_inference_error(self, err_msg):
        self.btn_generate.setEnabled(True)
        self.btn_generate.setText("🚀 Tạo mô hình 3D")
        self.set_status("❌ Lỗi kết nối Ollama!", "#DC2626")
        self.log(f"Lỗi kết nối:\n{err_msg}")
        QtWidgets.QMessageBox.critical(self, "Lỗi kết nối", err_msg)

    def on_fix_clicked(self):
        user_prompt = self.prompt_text.toPlainText().strip()
        failed_code = self.code_edit.toPlainText().strip()
        error_msg = self.engine.last_error

        if not failed_code or not error_msg:
            return

        fix_prompt = self.engine.build_fix_prompt(user_prompt, failed_code, error_msg)
        self.set_status("🔄 Đang gửi lỗi cho AI tự sửa...", "#D97706")
        self.log(f"\n--- [Yêu cầu sửa lỗi] ---\n{error_msg}")

        self.btn_fix.setEnabled(False)
        self.btn_fix.setText("⏳ Đang sửa...")

        self.worker = LLMInferenceWorker(self.engine, fix_prompt)
        self.worker.finished.connect(self.on_fix_success)
        self.worker.failed.connect(self.on_inference_error)
        self.worker.start()

    def on_fix_success(self, code):
        self.btn_fix.setEnabled(True)
        self.btn_fix.setText("🔧 Tự sửa lỗi (Fix)")
        self.engine.last_generated_code = code
        self.code_edit.setPlainText(code)

        self.set_status("⚙️ Đang chạy lại mã đã sửa...", "#2563EB")
        success, msg = self.engine.execute_code(code)

        if success:
            self.set_status("✅ Tự sửa lỗi thành công! Mô hình đã hiển thị.", "#16A34A")
            self.log("Sửa lỗi thành công!")
            self.btn_fix.setEnabled(False)
            self.tabs.setCurrentIndex(0)
            self.update_geometry_inspector()
        else:
            self.set_status("❌ Mã sửa vẫn chưa chuẩn.", "#DC2626")
            self.log(f"Vẫn lỗi:\n{msg}")

    def on_export_step_clicked(self):
        doc = App.ActiveDocument
        if not doc or not doc.Objects:
            QtWidgets.QMessageBox.warning(self, "Chưa có mô hình", "Hiện chưa có vật thể nào trong tài liệu để xuất!")
            return

        last_obj = doc.getObject("AICAD_Model") or doc.Objects[-1]
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Xuất mô hình STEP", f"{last_obj.Name}.step", "STEP Files (*.step *.stp)"
        )
        if file_path:
            try:
                import Import
                Import.export([last_obj], file_path)
                self.set_status(f"💾 Đã xuất file STEP: {os.path.basename(file_path)}", "#16A34A")
                self.log(f"Xuất file thành công: {file_path}")
            except Exception as e:
                self.set_status("❌ Lỗi xuất file STEP!", "#DC2626")
                self.log(f"Lỗi xuất file: {e}")

    def on_export_stl_clicked(self):
        doc = App.ActiveDocument
        if not doc or not doc.Objects:
            QtWidgets.QMessageBox.warning(self, "Chưa có mô hình", "Hiện chưa có vật thể nào trong tài liệu để xuất!")
            return

        last_obj = doc.getObject("AICAD_Model") or doc.Objects[-1]
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Xuất mô hình STL (In 3D)", f"{last_obj.Name}.stl", "STL Files (*.stl)"
        )
        if file_path:
            try:
                import MeshPart
                mesh = MeshPart.meshFromShape(Shape=last_obj.Shape, LinearDeflection=0.1, AngularDeflection=0.523)
                mesh.write(file_path)
                self.set_status(f"💾 Đã xuất file STL: {os.path.basename(file_path)}", "#16A34A")
                self.log(f"Xuất file STL thành công: {file_path}")
            except Exception as e:
                self.set_status("❌ Lỗi xuất file STL!", "#DC2626")
                self.log(f"Lỗi xuất file: {e}")

    def on_undo_clicked(self):
        doc = App.ActiveDocument
        if not doc or not doc.Objects:
            return
        last_obj = doc.getObject("AICAD_Model") or doc.Objects[-1]
        name = last_obj.Name
        doc.removeObject(name)
        doc.recompute()
        self.set_status(f"🗑 Đã xóa đối tượng: {name}", "#64748B")
        self.log(f"Đã gỡ bỏ: {name}")
        self.update_geometry_inspector()


_dock_widget_instance = None

def toggle_aicad_dock():
    global _dock_widget_instance
    if not hasattr(Gui, "getMainWindow") or Gui.getMainWindow() is None:
        return
    main_window = Gui.getMainWindow()
    if _dock_widget_instance is None:
        _dock_widget_instance = AICADDockWidget(main_window)
        main_window.addDockWidget(QtCore.Qt.RightDockWidgetArea, _dock_widget_instance)

    if _dock_widget_instance.isVisible():
        _dock_widget_instance.hide()
    else:
        _dock_widget_instance.show()
        _dock_widget_instance.raise_()
