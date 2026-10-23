# SPDX-License-Identifier: LGPL-2.1-or-later
"""
InitGui.py: Main entry point for FreeCAD GUI.
Delegates to aicad_wb module to ensure proper Python scoping.
"""

import os
import sys
import FreeCAD as App

wb_dir = os.path.join(App.getUserAppDataDir(), "Mod", "AICADWorkbench")
if wb_dir not in sys.path:
    sys.path.insert(0, wb_dir)

import aicad_wb
aicad_wb.setup_workbench()

