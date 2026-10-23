# BỘ TEST SUITE ĐÁNH GIÁ CHẤT LƯỢNG MÔ HÌNH TEXT-TO-CAD (CadQuery SFT)

Dành cho Tester / Thành viên QA kiểm thử và lập báo cáo so sánh trước & sau khi Fine-tune.

---

## 🎯 Hướng dẫn thực hiện Test
1. Mở FreeCAD 1.1, chọn Workbench **"AI CAD"**.
2. Đảm bảo ô Model ghi: **`cadquery-ai`** (hoặc `qwen2.5-coder:3b` nếu muốn test model gốc để so sánh).
3. Đảm bảo Chế độ mã là: **`CadQuery SFT Mode (Dataset sạch)`**.
4. Copy lần lượt từng câu prompt dưới đây dán vào ô nhập và bấm **"🚀 Tạo mô hình 3D"**.

---

## CẤP ĐỘ 1: KHỐI CƠ BẢN (PRIMITIVES & EXTRUSIONS)

### Test 1.1: Khối trụ tròn cơ bản
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Để dựng một đối tượng hình trụ, vẽ bản phác thảo hình tròn tại gốc tọa độ bán kính 20mm. Sau đó đùn theo hướng pháp tuyến một khoảng 50mm để tạo mô hình 3D.
```
- **Kỳ vọng:** Xuất hiện một hình trụ tròn đường kính 40mm, cao 50mm.

### Test 1.2: Khối hộp chữ nhật
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một khối hộp chữ nhật có kích thước dài 70mm, rộng 50mm và cao 25mm.
```
- **Kỳ vọng:** Xuất hiện khối hộp đúng kích thước 70x50x25mm.

---

## CẤP ĐỘ 2: PHÉP CẮT KHỐI & ĐỤC LỖ (BOOLEAN CUTS)

### Test 2.1: Ống trụ tròn rỗng
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một hình ống trụ tròn rỗng có đường kính ngoài 50mm, đường kính trong 30mm và chiều cao 60mm.
```
- **Kỳ vọng:** Khối trụ bị khoét rỗng xuyên suốt từ trên xuống dưới, thành ống dày 10mm.

### Test 2.2: Khối hộp đục lỗ tâm
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một khối hộp chữ nhật kích thước 80x60x20mm có khoét một lỗ tròn xuyên suốt đường kính 18mm ở chính giữa tâm mặt trên.
```
- **Kỳ vọng:** Khối hộp có lỗ tròn đục xuyên tâm.

---

## CẤP ĐỘ 3: GHÉP NỐI & TAY CẦM (UNIONS & TRANSFORMS)

### Test 3.1: Hộp có tay cầm nối tiếp (Mẫu chuẩn SFT)
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một khối hộp chữ nhật kích thước 60x40x15mm. Sau đó tạo thêm một thanh tay cầm dài 70mm rộng 12mm dày 12mm gắn nối tiếp vào mép ngoài của hộp.
```
- **Kỳ vọng:** Hai khối đặc được hợp nhất thành một vật thể duy nhất (Union).

### Test 3.2: Trục bậc cơ khí 2 đoạn
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một chi tiết trục cơ khí gồm hai đoạn hình trụ nối tiếp nhau: đoạn thứ nhất đường kính 30mm dài 40mm, đoạn thứ hai đường kính 16mm dài 30mm.
```
- **Kỳ vọng:** Chi tiết trục bậc 2 tầng đồng trục.

---

## CẤP ĐỘ 4: BÀI TOÁN KỸ THUẬT PHỨC TẠP (COMPLEX MECHANICAL)

### Test 4.1: Mặt bích vuông có 4 lỗ bắt vít M4
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một mặt bích vuông kích thước 80x80x10mm có 4 lỗ bắt bu-lông M4 (đường kính 4mm) bố trí ở 4 góc cách mép 10mm.
```
- **Kỳ vọng:** Mặt bích phẳng có 4 lỗ tròn đối xứng cách đều 4 góc 10mm.

### Test 4.2: Giá đỡ chữ L có gân tăng cứng
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một giá đỡ góc chữ L kích thước 60x40x60mm thành dày 6mm, có một gân tăng cứng tam giác dày 6mm ở chính giữa nối hai cạnh.
```
- **Kỳ vọng:** Giá đỡ chữ L có gân trợ lực tam giác nối ở giữa.

### Test 4.3: Vỏ hộp linh kiện điện tử (Enclosure)
```text
Dựa vào mô tả sau đây, hãy tạo mã CadQuery để tạo mô hình 3D:
Tạo một vỏ hộp dự án rỗng không có nắp kích thước ngoài 80x50x25mm, độ dày thành và đáy là 2mm.
```
- **Kỳ vọng:** Khối hộp rỗng bên trong, viền thành và đáy đúng 2mm.

---

## 📊 BẢNG GHI NHẬN KẾT QUẢ (SCORECARD)

| Bài Test | Tỷ lệ chạy được mã (Syntax) | Độ chuẩn kích thước | Thời gian sinh (giây) | Ghi chú |
| :--- | :---: | :---: | :---: | :--- |
| Test 1.1 (Trụ) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 1.2 (Hộp) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 2.1 (Ống) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 2.2 (Lỗ tâm) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 3.1 (Hộp + Tay cầm) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 3.2 (Trục bậc) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 4.1 (Mặt bích 4 lỗ) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 4.2 (Giá đỡ chữ L) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |
| Test 4.3 (Vỏ hộp rỗng) | [ ] Đạt / [ ] Lỗi | [ ] Đúng / [ ] Sai | ...s | |

