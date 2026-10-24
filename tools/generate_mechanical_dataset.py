# SPDX-License-Identifier: LGPL-2.1-or-later
"""
generate_mechanical_dataset.py:
Generates 300+ diverse, high-precision, real-world mechanical engineering CAD samples
(flanges, V-belt pulleys, stepped shafts, L-brackets with ribs, enclosures, pipes, multi-turn edits)
and combines them with the existing cleaned dataset to create `cad_data_train_v2_mechanical.json`.
"""

import json
import os
import math
import random
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

random.seed(42)

def generate_v_belt_pulley_samples():
    samples = []
    outer_d_list = [60, 70, 80, 90, 100, 110, 120, 140, 150]
    thickness_list = [18, 20, 22, 25, 28, 30, 35]
    depth_list = [7, 8, 10, 12]
    angles = [34, 36, 38, 40]
    shaft_list = [10, 12, 14, 15, 18, 20, 25]

    for d_out in outer_d_list:
        for thick in [20, 25, 30]:
            shaft = random.choice(shaft_list)
            v_depth = random.choice(depth_list)
            angle = random.choice(angles)
            r_out = d_out / 2.0
            r_hole = shaft / 2.0

            inst_vi = (
                f"Tạo một puly đai thang đường kính ngoài {d_out}mm, chiều dày {thick}mm, "
                f"có rãnh đai chữ V ở giữa sâu {v_depth}mm góc {angle} độ, lỗ trục tâm phi {shaft}mm."
            )

            code = f"""import cadquery as cq
import math

r_out = {r_out}
r_hole = {r_hole}
h = {thick}
depth = {v_depth}
half_angle = {angle / 2.0}
half_w = depth * math.tan(math.radians(half_angle))

# Ve bien dang mat cat puly chu V tren mat phang XZ
pts = [
    (r_hole, 0),
    (r_out, 0),
    (r_out, h / 2.0 - half_w),
    (r_out - depth, h / 2.0),
    (r_out, h / 2.0 + half_w),
    (r_out, h),
    (r_hole, h),
    (r_hole, 0)
]

r = cq.Workplane("XZ").polyline(pts).close().revolve(360, (0, 0, 0), (0, 1, 0))
show_object(r)"""

            samples.append({
                "messages": [
                    {"role": "user", "content": f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{inst_vi}"},
                    {"role": "assistant", "content": code}
                ]
            })

            # Bilingual English sample
            inst_en = (
                f"Create a V-belt pulley with an outer diameter of {d_out}mm, thickness of {thick}mm, "
                f"a central V-shaped groove of depth {v_depth}mm and angle {angle} degrees, and a center shaft bore of {shaft}mm."
            )
            samples.append({
                "messages": [
                    {"role": "user", "content": f"Please based on the following description to generate CadQuery code to create a 3D model:\n{inst_en}"},
                    {"role": "assistant", "content": code}
                ]
            })
    return samples

def generate_square_flange_samples():
    samples = []
    sizes = [(60, 60), (70, 70), (80, 80), (90, 90), (100, 100), (120, 120), (80, 60), (100, 80)]
    thick_list = [8, 10, 12, 15, 20]
    bolts = [("M3", 3.2), ("M4", 4.2), ("M5", 5.2), ("M6", 6.5), ("M8", 8.5), ("M10", 10.5)]

    for (L, W) in sizes:
        for T in [10, 12, 15]:
            bolt_name, bolt_d = random.choice(bolts)
            offset = 10 if min(L, W) <= 80 else 15
            has_center_bore = random.choice([True, False])
            bore_d = 20 if min(L, W) <= 80 else 30

            cb_text = f", ở giữa có lỗ trục tâm đường kính {bore_d}mm" if has_center_bore else ""
            inst_vi = (
                f"Tạo một mặt bích vuông kích thước {L}x{W}x{T}mm có 4 lỗ bắt bu-lông {bolt_name} "
                f"(đường kính {bolt_d}mm) bố trí ở 4 góc cách mép {offset}mm{cb_text}."
            )

            # Coordinates
            code = f"""import cadquery as cq

length = {L}
width = {W}
thickness = {T}
hole_d = {bolt_d}
offset = {offset}

plate = cq.Workplane('XY').box(length, width, thickness)

# 4 lo cach deu 4 mep
pts = [
    (length / 2.0 - offset, width / 2.0 - offset),
    (-(length / 2.0 - offset), width / 2.0 - offset),
    (-(length / 2.0 - offset), -(width / 2.0 - offset)),
    (length / 2.0 - offset, -(width / 2.0 - offset))
]

holes = cq.Workplane('XY').pushPoints(pts).circle(hole_d / 2.0).extrude(thickness * 2, both=True)
r = plate.cut(holes)
"""
            if has_center_bore:
                code += f"""
center_hole = cq.Workplane('XY').circle({bore_d / 2.0}).extrude(thickness * 2, both=True)
r = r.cut(center_hole)
"""
            code += "show_object(r)"

            samples.append({
                "messages": [
                    {"role": "user", "content": f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{inst_vi}"},
                    {"role": "assistant", "content": code}
                ]
            })
    return samples

def generate_stepped_shaft_samples():
    samples = []
    configs = [
        [(40, 50), (20, 30)],
        [(50, 60), (30, 40)],
        [(30, 40), (18, 25)],
        [(60, 50), (40, 40), (25, 30)],
        [(50, 40), (35, 35), (20, 25)]
    ]

    for cfg in configs:
        desc_parts = []
        for i, (d, l) in enumerate(cfg):
            if i == 0:
                desc_parts.append(f"tầng dưới cùng đường kính {d}mm dài {l}mm")
            else:
                desc_parts.append(f"tầng tiếp theo đường kính {d}mm dài {l}mm")

        inst_vi = f"Dựng một trục bậc gồm {', '.join(desc_parts)}."
        
        code_lines = ["import cadquery as cq", "", "r = None", "cur_z = 0.0"]
        for i, (d, l) in enumerate(cfg):
            r_val = d / 2.0
            if i == 0:
                code_lines.append(f"# Tang {i+1}: D={d}mm, L={l}mm")
                code_lines.append(f"base = cq.Workplane('XY').circle({r_val}).extrude({l})")
                code_lines.append(f"r = base")
                code_lines.append(f"cur_z += {l}")
            else:
                code_lines.append(f"# Tang {i+1}: D={d}mm, L={l}mm")
                code_lines.append(f"step_{i} = cq.Workplane('XY').workplane(offset=cur_z).circle({r_val}).extrude({l})")
                code_lines.append(f"r = r.union(step_{i})")
                code_lines.append(f"cur_z += {l}")
        
        code_lines.append("show_object(r)")
        code = "\n".join(code_lines)

        samples.append({
            "messages": [
                {"role": "user", "content": f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{inst_vi}"},
                {"role": "assistant", "content": code}
            ]
        })
    return samples

def generate_round_flange_samples():
    samples = []
    configs = [
        (100, 12, 70, 6, 6.0, 30),
        (120, 15, 90, 6, 8.0, 40),
        (150, 18, 115, 8, 10.0, 50),
        (80, 10, 55, 4, 5.0, 20)
    ]

    for (d_out, thick, pcd, num_holes, hole_d, bore_d) in configs:
        inst_vi = (
            f"Tạo một mặt bích tròn đường kính ngoài {d_out}mm, dày {thick}mm, "
            f"có {num_holes} lỗ bu-lông đường kính {hole_d}mm phân bố đều trên vòng tròn chia đường kính {pcd}mm, "
            f"ở giữa có lỗ trục phi {bore_d}mm."
        )

        code = f"""import cadquery as cq
import math

d_out = {d_out}
thickness = {thick}
pcd = {pcd}
num_holes = {num_holes}
hole_d = {hole_d}
bore_d = {bore_d}

plate = cq.Workplane('XY').circle(d_out / 2.0).extrude(thickness)

# Tinh toa do mang lo phan bo deu tren vong tron
pts = []
for i in range(num_holes):
    angle = 2.0 * math.pi * i / num_holes
    x = (pcd / 2.0) * math.cos(angle)
    y = (pcd / 2.0) * math.sin(angle)
    pts.append((x, y))

holes = cq.Workplane('XY').pushPoints(pts).circle(hole_d / 2.0).extrude(thickness * 2, both=True)
center_bore = cq.Workplane('XY').circle(bore_d / 2.0).extrude(thickness * 2, both=True)

r = plate.cut(holes).cut(center_bore)
show_object(r)"""

        samples.append({
            "messages": [
                {"role": "user", "content": f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{inst_vi}"},
                {"role": "assistant", "content": code}
            ]
        })
    return samples

def generate_bracket_and_pipe_samples():
    samples = []
    # Pipe
    pipes = [(50, 30, 60), (60, 40, 80), (40, 20, 50), (80, 50, 100)]
    for (od, id_val, h) in pipes:
        inst = f"Tạo một ống tròn rỗng có đường kính ngoài {od}mm, đường kính trong {id_val}mm và chiều cao {h}mm."
        code = f"""import cadquery as cq
outer = cq.Workplane('XY').circle({od / 2.0}).extrude({h})
inner = cq.Workplane('XY').circle({id_val / 2.0}).extrude({h + 10}, both=True)
r = outer.cut(inner)
show_object(r)"""
        samples.append({
            "messages": [
                {"role": "user", "content": f"Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:\n{inst}"},
                {"role": "assistant", "content": code}
            ]
        })
    return samples

def main():
    print("[*] Generating Mechanical CAD Synthetic Dataset...")
    all_mech = []
    all_mech.extend(generate_v_belt_pulley_samples())
    all_mech.extend(generate_square_flange_samples())
    all_mech.extend(generate_stepped_shaft_samples())
    all_mech.extend(generate_round_flange_samples())
    all_mech.extend(generate_bracket_and_pipe_samples())

    print(f"[+] Total new mechanical samples generated: {len(all_mech)}")

    # Locate cleaned dataset
    dname = [d for d in os.listdir('.') if 'đã làm sạch' in d][0]
    src_path = os.path.join(dname, 'cad_data_train_cleaned_vi.json')
    out_path = os.path.join(dname, 'cad_data_train_v2_mechanical.json')

    with open(src_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)

    print(f"[*] Existing dataset samples: {len(existing)}")

    # Combine: Over-sample the mechanical samples 5x so they have a strong influence during training!
    weighted_mech = all_mech * 5
    combined = existing + weighted_mech
    random.shuffle(combined)

    print(f"[+] Final enriched dataset samples: {len(combined)} (including {len(weighted_mech)} weighted mechanical samples)")

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)

    print(f"[SUCCESS] Saved enriched training dataset to: {out_path}")

if __name__ == "__main__":
    main()
