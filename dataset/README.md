# Dataset Báo Cáo: Dữ Liệu Huấn Luyện Text-to-CAD (CadQuery / FreeCAD)

Tập dữ liệu này được thiết kế và làm sạch phục vụ bài toán **Supervised Fine-Tuning (SFT)** cho mô hình ngôn ngữ lớn (LLM) sinh mã nguồn CAD (Text-to-CAD) tích hợp vào **AICADWorkbench / FreeCAD**.

---

## 1. Cấu Trúc Thư Mục

```
dataset/
├── raw/                                           # Dữ liệu gốc chưa qua xử lý
│   ├── CAD-Coder_train_high_validation.docx       # Tài liệu đặc tả gốc của tác giả
│   ├── cad_data_train_high.json                   # Tập huấn luyện thô gốc (8.177 mẫu)
│   └── cad_data_validation.json                   # Tập kiểm định thô gốc (8.817 mẫu)
│
└── cleaned/                                       # Dữ liệu đã làm sạch & chuẩn hóa song ngữ
    ├── cad_data_train_cleaned_en.json             # Tập train tiếng Anh đã kiểm định (8.177 mẫu)
    ├── cad_data_train_cleaned_vi.json             # Tập train tiếng Việt đã dịch kỹ thuật (8.177 mẫu)
    ├── cad_data_train_cleaned_bilingual.json      # Tập train Song ngữ EN + VI (16.354 mẫu)
    ├── cad_data_validation_cleaned_en.json        # Tập val tiếng Anh đã kiểm định (8.817 mẫu)
    ├── cad_data_validation_cleaned_vi.json        # Tập val tiếng Việt đã dịch kỹ thuật (8.817 mẫu)
    └── cad_data_validation_cleaned_bilingual.json # Tập val Song ngữ EN + VI (17.634 mẫu)
```

---

## 2. Tiêu Chuẩn & Quy Trình Làm Sạch (Cleaning Pipeline)

1. **Kiểm tra tính hợp lệ cú pháp Python (Python AST Validation):**
   * Toàn bộ mã nguồn sinh ra bởi `assistant` được parse qua thư viện `ast` của Python.
   * Đảm bảo 100% mẫu không bị lỗi cú pháp (`SyntaxError`), không khuyết thiếu thụt dòng (indentation) hay đóng ngoặc.
2. **Kiểm tra tính tương thích CadQuery API:**
   * Xác nhận sự hiện diện của thư viện `cadquery` (`import cadquery as cq` hoặc các hàm `cq.Workplane`).
3. **Lọc trùng lặp (Deduplication):**
   * Quét toàn bộ nội dung prompt để loại bỏ các mẫu trùng nhau hoàn toàn.
4. **Dịch thuật & Chuẩn hóa thuật ngữ CAD chuyên sâu (Vietnamese CAD Technical Translation):**
   * Các prompt tiếng Anh được chuyển thể sang tiếng Việt với hệ thống thuật ngữ cơ khí chính xác:
     * *Coordinate system* $\rightarrow$ Hệ tọa độ
     * *Euler angles* $\rightarrow$ Các góc Euler
     * *Translation vector* $\rightarrow$ Vectơ tịnh tiến
     * *Two-dimensional sketch* $\rightarrow$ Bản phác thảo hai chiều (2D)
     * *Closed loop / Line / Arc / Circle* $\rightarrow$ Vòng lặp khép kín / Đoạn thẳng / Cung tròn / Hình tròn
     * *Normal direction* $\rightarrow$ Hướng pháp tuyến
     * *Extrude* $\rightarrow$ Đùn (extrude)
     * *Solid body* $\rightarrow$ Khối đặc 3D
   * Bảo toàn 100% tọa độ `(x, y)`, vectơ `[x, y, z]`, các hằng số float và tham số kỹ thuật.

---

## 3. Thống Kê Chi Tiết Dữ Liệu

| Tên File | Ngôn Ngữ | Số Lượng Mẫu | Dung Lượng | Vai Trò |
| :--- | :---: | :---: | :---: | :--- |
| `cad_data_train_cleaned_en.json` | Tiếng Anh | 8.177 | ~17.2 MB | Train mô hình hiểu tiếng Anh |
| `cad_data_train_cleaned_vi.json` | Tiếng Việt | 8.177 | ~18.3 MB | Train mô hình hiểu tiếng Việt |
| `cad_data_train_cleaned_bilingual.json` | **Song ngữ** | **16.354** | **~35.5 MB** | **Khuyên dùng:** Train model hiểu cả EN và VI |
| `cad_data_validation_cleaned_en.json` | Tiếng Anh | 8.817 | ~22.7 MB | Đánh giá độ chính xác (EN) |
| `cad_data_validation_cleaned_vi.json` | Tiếng Việt | 8.817 | ~24.3 MB | Đánh giá độ chính xác (VI) |
| `cad_data_validation_cleaned_bilingual.json` | **Song ngữ** | **17.634** | **~47.0 MB** | Đánh giá toàn diện cả 2 ngôn ngữ |

---

## 4. Hướng Dẫn Sử Dụng Nhanh Khi Fine-Tune (Unsloth / TRL)

```python
from datasets import load_dataset

# Nạp tập dữ liệu song ngữ đã làm sạch
dataset = load_dataset("json", data_files={
    "train": "dataset/cleaned/cad_data_train_cleaned_bilingual.json",
    "validation": "dataset/cleaned/cad_data_validation_cleaned_bilingual.json"
})

print(dataset["train"][0])
# messages: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
```
