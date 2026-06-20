# VVIP PUBG — Macro giảm giật

Phần mềm hỗ trợ giảm giật khi bắn trong PUBG. Bạn chọn súng + phụ kiện, app tự tính lực kéo chuột và áp dụng khi giữ chuột trái (bắn).

> **Cảnh báo:** Macro vi phạm điều khoản PUBG. Dùng có thể bị khóa tài khoản — tự chịu rủi ro.

---

## Yêu cầu

- Windows 10/11
- Python 3.10 trở lên
- Chạy **quyền Administrator** (khuyến nghị) để macro hoạt động ổn định khi game full màn hình
- PUBG ở chế độ **Borderless** hoặc **Windowed** (overlay và nhận diện màn hình hoạt động tốt hơn)

---

## Cài đặt

1. Mở thư mục dự án (ví dụ `macro_pubg`).
2. Cài thư viện:

```bash
pip install -r requirements.txt
```

3. (Tuỳ chọn) Nếu dùng **tự động nhận diện súng**, cần cài thêm [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) và thêm vào PATH.

---

## Chạy phần mềm

```bash
python main.py
```

Nên chuột phải → **Run as administrator** khi chạy lần đầu.

Cửa sổ app có 3 tab chính. Mọi cài đặt được **lưu tự động** vào `config.json`.

---

## Hướng dẫn nhanh (5 bước)

### Bước 1 — Bật macro

Góc trên phải cửa sổ app: bật công tắc **BẬT / TẮT** (hoặc nhấn **F8** trong game).

### Bước 2 — Chọn súng và phụ kiện

Vào tab **🔫 Súng & Phụ kiện**:

- **Ô Súng 1** và **Ô Súng 2** tương ứng 2 vũ khí trong game.
- Chọn tên súng, scope, họng súng, tay cầm, báng, băng đạn.
- Kéo thanh **Độ nhạy (sensitivity)** cho khớp DPI và sens trong game của bạn (bắt đầu từ `1.00`, chỉnh dần).

Phần dưới mỗi ô hiển thị RPM, hệ số giảm giật và lực kéo theo từng giai đoạn băng đạn.

### Bước 3 — Chọn súng đang dùng

Trong game, nhấn phím **1** hoặc **2** (mặc định) để chọn Ô Súng 1 hoặc 2 — giống đổi súng chính/phụ trong PUBG.

### Bước 4 — Bắn

- **Chuột trái** = bắn (giữ để macro kéo chuột xuống).
- **Chuột phải** = ngắm (ADS).

Mặc định macro **chỉ kéo khi đang ngắm** (giữ cả chuột trái + chuột phải). Có thể tắt ở tab Cài đặt.

### Bước 5 — Chỉnh nếu giật chưa khớp

- Tăng/giảm **Độ nhạy** nếu kéo quá mạnh hoặc quá yếu.
- Vào tab **⚙️ Cài đặt** → sửa chỉ số giật từng súng hoặc hệ số phụ kiện nếu cần tinh chỉnh sâu hơn.

---

## Các tab trong app

| Tab | Chức năng |
|-----|-----------|
| **🖥️ Thông tin máy** | Xem CPU, RAM, GPU, ổ đĩa |
| **🔫 Súng & Phụ kiện** | Cấu hình 2 ô súng, độ nhạy, xem profile giảm giật |
| **⚙️ Cài đặt** | Phím nóng, ADS, CCW, overlay, auto-detect, chỉnh số giật |

---

## Phím nóng mặc định

| Phím | Tác dụng |
|------|-----------|
| **1** | Chọn Ô Súng 1 |
| **2** | Chọn Ô Súng 2 |
| **F8** | Bật / tắt macro nhanh |
| **Del** | Bật / tắt overlay trong game |
| **Tab** | Nhận diện súng khi mở balo (nếu bật Auto-detect) |
| **F10** | Chụp màn hình + vẽ các ô nhận diện (debug) |

Có thể đổi phím 1, 2, F8, Del trong tab **⚙️ Cài đặt → Phím nóng**.

---

## Tính năng bổ sung

### Overlay trong game

Thanh ngang ở **đáy màn hình** hiển thị súng và phụ kiện đang dùng — không cần Alt-Tab. Bấm **Del** hoặc nút trong app để bật/tắt.

### Tự động nhận diện súng

1. Bật **Auto-detect** trong tab Cài đặt.
2. Trong game, mở balo (phím **Tab**).
3. App tự đọc tên súng và điền vào Ô 1 / Ô 2.

Nút **🔍 Nhận diện ngay** dùng để thử thủ công.

### Macro CCW (trượt khi chạy)

Bật trong tab Cài đặt. Giữ **Shift trước, rồi W** (cả hai cùng lúc) đủ thời gian chờ → tự trượt. **W trước Shift** sẽ không kích hoạt.

---

## Mẹo sử dụng

1. **Chạy Admin** nếu macro không kéo chuột trong game.
2. **Borderless / Windowed** — tránh chế độ Exclusive Fullscreen nếu overlay hoặc nhận diện không hoạt động.
3. **Độ nhạy** là chỉnh nhanh nhất — thử từ `0.8` → `1.2` cho đến khi ổn.
4. Cấu hình lưu trong `config.json`. Nút **💾 Lưu ngay** ghi file thủ công; **↺ Khôi phục mặc định** xóa toàn bộ chỉnh sửa.
5. Chế độ **TEST** (tab Cài đặt) đọc từ ảnh `shot.png` thay vì màn hình — dùng khi debug nhận diện.

---

## Công cụ nâng cao (dòng lệnh)

| Lệnh | Mục đích |
|------|----------|
| `python calibrate.py` | Kiểm tra vị trí khung nhận diện tên súng |
| `python learn.py list` | Xem thư viện icon phụ kiện |
| `python learn.py draft` | Cắt icon phụ kiện chưa nhận ra vào thư mục `draft/` |

Chi tiết xem docstring trong `calibrate.py` và `learn.py`.

---

## Cấu trúc thư mục chính

```
macro_pubg/
├── main.py           # Chạy app
├── config.json       # Cấu hình đã lưu
├── backend/          # Engine giảm giật, nhận diện
├── web/              # Giao diện app
├── templates/        # Icon mẫu phụ kiện
└── requirements.txt  # Thư viện Python
```

---

**VVIP PUBG · by hoangks5**
