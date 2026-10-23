# Báo Cáo Quy Trình Làm Sạch Dữ Liệu CAD (CadQuery)

Dữ liệu Supervised Fine-Tuning (SFT) Text-to-CAD cho FreeCAD / AICADWorkbench.

## 1. Các cải tiến đã thực hiện
1. **Khử rò rỉ mã nguồn (Data Leakage):** Loại bỏ toàn bộ 88 mẫu trong tập Train có code trùng lặp với tập Validation.
2. **Dịch Tiếng Việt chuẩn hóa 100%:** Loại bỏ hoàn toàn câu lai Anh–Việt, sửa lỗi lồng `đùn (Đùn (extrude))` thành `đùn (extrude)`, bảo toàn 100% tọa độ và số thực.
3. **Loại bỏ cột `model_path`:** Chỉ giữ cấu trúc `messages` chuẩn SFTTrainer.

## 2. Thống kê dữ liệu
- **Train sạch:** 8089 mẫu (gốc: 8177, loại 88 mẫu rò rỉ)
- **Validation sạch:** 8817 mẫu
- **Tập Train song ngữ (bilingual):** 16178 mẫu
- **Tập Val song ngữ (bilingual):** 17634 mẫu
