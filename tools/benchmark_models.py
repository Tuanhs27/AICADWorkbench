# SPDX-License-Identifier: LGPL-2.1-or-later
"""
tools/benchmark_models.py: Automated benchmark script to evaluate Fine-tuned Text-to-CAD models.
Calculates Execution Pass@1, Valid Solid Rate, and Geometric Statistics.
"""

import os
import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Automatically inject FreeCAD bin and lib paths and C++ DLLs
_DLL_COOKIES = []
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

MODULE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

import aicad_engine

BENCHMARK_PROMPTS = [
    # Cấp độ 1: Khối cơ bản
    ("1.1 Trụ tròn", "Tạo một khối trụ tròn có bán kính 20mm và chiều cao 50mm tại gốc tọa độ."),
    ("1.2 Hộp chữ nhật", "Tạo một khối hộp chữ nhật có kích thước dài 70mm, rộng 50mm và cao 25mm."),
    
    # Cấp độ 2: Cắt đục lỗ
    ("2.1 Ống tròn rỗng", "Tạo một hình ống trụ tròn rỗng có đường kính ngoài 50mm, đường kính trong 30mm và chiều cao 60mm."),
    ("2.2 Hộp khoét tâm", "Tạo một khối hộp chữ nhật 80x60x20mm có khoét một lỗ tròn xuyên suốt đường kính 18mm ở chính giữa."),
    
    # Cấp độ 3: Khối tròn xoay & Bậc
    ("3.1 Trục bậc 2 tầng", "Tạo một chi tiết trục cơ khí gồm hai đoạn hình trụ đồng trục: đoạn thứ nhất đường kính 30mm dài 40mm, đoạn thứ hai đường kính 16mm dài 30mm."),
    ("3.2 Puly rãnh V", "Tạo một puly đai thang đường kính ngoài 80mm, chiều dày 25mm, có rãnh đai chữ V ở giữa sâu 10mm góc 38 độ, lỗ trục tâm phi 15mm."),
    
    # Cấp độ 4: Cơ khí thực tế
    ("4.1 Mặt bích tròn 6 lỗ", "Tạo một mặt bích tròn đường kính ngoài 100mm, dày 12mm, có 6 lỗ bu-lông đường kính 6mm phân bố đều trên vòng chia đường kính 70mm, ở giữa có lỗ trục phi 30mm."),
    ("4.2 Mặt bích vuông 4 lỗ", "Tạo một mặt bích vuông kích thước 80x80x10mm có 4 lỗ bắt bu-lông đường kính 5mm ở 4 góc và một lỗ tâm phi 30mm."),
    ("4.3 Giá đỡ chữ L", "Tạo một giá đỡ góc chữ L kích thước 60x60mm thành dày 6mm, dài 40mm."),
    ("4.4 Hộp linh kiện", "Tạo một vỏ hộp chữ nhật rỗng hở nắp kích thước ngoài 80x50x25mm, bề dày thành và đáy là 3mm.")
]


def run_benchmark(model_name="cadquery-ai:latest"):
    print(f"\n=======================================================")
    print(f"🚀 BẮT ĐẦU ĐÁNH GIÁ MÔ HÌNH: {model_name}")
    print(f"=======================================================\n")

    eng = aicad_engine.AICADEngine()
    eng.model = model_name

    results = []
    total_time = 0.0

    for idx, (title, prompt) in enumerate(BENCHMARK_PROMPTS, 1):
        print(f"[{idx}/{len(BENCHMARK_PROMPTS)}] Đang kiểm thử: {title} ...", end=" ", flush=True)
        t0 = time.time()
        
        # 1. Đo thời gian sinh mã
        try:
            # Query Ollama
            formatted_prompt = f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{prompt}"
            raw_resp = eng.query_ollama(formatted_prompt, temperature=0.1)
            code = eng.extract_code(raw_resp)
            gen_time = time.time() - t0
        except Exception as e:
            gen_time = time.time() - t0
            results.append({
                "title": title,
                "syntax_ok": False,
                "solid_ok": False,
                "stats": None,
                "time": gen_time,
                "error": str(e)
            })
            print(f"❌ LỖI SINH MÃ ({gen_time:.2f}s): {e}")
            continue

        # 2. Kiểm thử thực thi trên FreeCAD CAD Bridge
        if aicad_engine.App:
            try:
                if aicad_engine.App.ActiveDocument:
                    aicad_engine.App.closeDocument(aicad_engine.App.ActiveDocument.Name)
            except Exception:
                pass
            aicad_engine.App.newDocument("BenchmarkDoc")

        success, msg = eng.execute_code(code)
        stats = eng.get_model_geometry_stats() if success else None
        
        solid_ok = False
        if stats and (stats.get("solids", 0) > 0 or stats.get("faces", 0) > 0):
            solid_ok = True

        total_time += gen_time
        results.append({
            "title": title,
            "syntax_ok": success,
            "solid_ok": solid_ok,
            "stats": stats,
            "time": gen_time,
            "error": msg if not success else ""
        })

        if success and solid_ok:
            vol = stats.get("volume", 0.0)
            print(f"✅ ĐẠT ({gen_time:.2f}s | Thể tích: {vol:,.1f} mm³)")
        elif success and not solid_ok:
            print(f"⚠️ CHẠY ĐƯỢC NHƯNG KHÔNG TẠO KHỐI ({gen_time:.2f}s)")
        else:
            err_line = msg.strip().split("\n")[-1] if msg else "Unknown"
            print(f"❌ LỖI THỰC THI ({gen_time:.2f}s | {err_line})")

    # 3. Tổng hợp Báo cáo Đánh giá
    total = len(results)
    syntax_passes = sum(1 for r in results if r["syntax_ok"])
    solid_passes = sum(1 for r in results if r["solid_ok"])
    pass_rate = (syntax_passes / total) * 100
    solid_rate = (solid_passes / total) * 100
    avg_time = total_time / total if total > 0 else 0.0

    print("\n" + "=" * 65)
    print(f"📊 BẢNG TỔNG HỢP ĐÁNH GIÁ (MODEL: {model_name})")
    print("=" * 65)
    print(f"• Tổng số bài test:               {total}")
    print(f"• Tỷ lệ biên dịch thành công:      {pass_rate:.1f}% ({syntax_passes}/{total} Pass@1)")
    print(f"• Tỷ lệ tạo khối CAD hợp lệ:      {solid_rate:.1f}% ({solid_passes}/{total})")
    print(f"• Thời gian phản hồi trung bình:   {avg_time:.2f} giây/prompt")
    print("=" * 65)

    print("\n| Bài test | Biên dịch (Pass@1) | Hợp lệ CAD | Kích thước bao (X x Y x Z) | Thời gian |")
    print("| :--- | :---: | :---: | :---: | :---: |")
    for r in results:
        s_ok = "✅ Đạt" if r["syntax_ok"] else "❌ Lỗi"
        v_ok = "✅ Hợp lệ" if r["solid_ok"] else "❌ Không"
        st = r["stats"]
        dim_str = f"{st['x']:.1f} x {st['y']:.1f} x {st['z']:.1f} mm" if st else "--"
        print(f"| {r['title']} | {s_ok} | {v_ok} | {dim_str} | {r['time']:.2f}s |")
    print("\n")


if __name__ == "__main__":
    target_model = sys.argv[1] if len(sys.argv) > 1 else "cadquery-ai:latest"
    run_benchmark(target_model)

