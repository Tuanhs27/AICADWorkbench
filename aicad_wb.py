# SPDX-License-Identifier: LGPL-2.1-or-later
"""
aicad_wb.py: Defines the FreeCAD Workbench and Toolbar Commands for AI CAD.
"""

import os
import FreeCAD as App
import FreeCADGui as Gui

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(MODULE_DIR, "resources", "aicad_icon.svg")


class OpenAICADPanelCommand:
    """Command to toggle the AICAD Assistant panel"""

    def GetResources(self):
        pixmap = ICON_PATH if os.path.exists(ICON_PATH) else "Part_Box"
        return {
            "Pixmap": pixmap,
            "MenuText": "Mở Bảng AI Text-to-CAD",
            "ToolTip": "Mở bảng trợ lý AI tạo mô hình CAD từ văn bản",
        }

    def Activated(self):
        import aicad_gui
        aicad_gui.toggle_aicad_dock()

    def IsActive(self):
        return True


BaseWorkbench = getattr(Gui, "Workbench", globals().get("Workbench", object))


class AICADWorkbench(BaseWorkbench):
    """AI CAD Workbench class"""

    MenuText = "AI CAD"
    ToolTip = "Text-to-CAD Workbench sử dụng Local LLM"
    Icon = ICON_PATH if os.path.exists(ICON_PATH) else "Part_Box"

    def Initialize(self):
        """Called when the workbench is activated for the first time"""
        self.appendToolbar("AI CAD Tools", ["AICAD_TogglePanel"])
        self.appendMenu("AI CAD", ["AICAD_TogglePanel"])

    def Activated(self):
        try:
            import aicad_gui
            aicad_gui.toggle_aicad_dock()
        except Exception:
            pass

    def Deactivated(self):
        pass

    def GetClassName(self):
        return "Gui::PythonWorkbench"


def setup_workbench():
    """Register commands and workbench into FreeCAD GUI"""
    if hasattr(Gui, "addCommand"):
        Gui.addCommand("AICAD_TogglePanel", OpenAICADPanelCommand())

    if hasattr(Gui, "addWorkbench"):
        Gui.addWorkbench(AICADWorkbench())

