# -*- coding: utf-8 -*-
"""
Hiệu chỉnh / kiểm thử nhận diện súng (chạy riêng, chưa ghép vào app).

Cách dùng:
  python calibrate.py "C:\\duong_dan\\anh_inventory.png"   # test trên ảnh có sẵn
  python calibrate.py                                       # chụp LIVE màn hình hiện tại

Kết quả:
  - In ra: OCR đọc được gì + súng nhận ra + điểm khớp.
  - Lưu vào ./debug/: full_boxes.png (ảnh có 2 khung vàng) và crop_*.png.
    Mở full_boxes.png xem 2 khung vàng đã trùm đúng TÊN SÚNG chưa.
    Nếu chưa, sửa toạ độ trong backend/vision.py -> DEFAULT_REGIONS rồi chạy lại.
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import cv2
except Exception:
    print("Chưa cài opencv-python:  pip install -r requirements.txt")
    sys.exit(1)

from backend.vision import WeaponDetector, pytesseract, mss

det = WeaponDetector()

# kiểm tra môi trường
if pytesseract is None:
    print("[!] Chưa cài pytesseract (pip install pytesseract)")
if pytesseract is not None:
    try:
        ver = pytesseract.get_tesseract_version()
        print(f"[ok] Tesseract {ver}")
    except Exception:
        print("[!] Không tìm thấy Tesseract.exe — cài bản UB Mannheim và/hoặc")
        print("    sửa TESSERACT_PATH trong backend/vision.py")

img = None
if len(sys.argv) > 1:
    path = sys.argv[1]
    img = cv2.imread(path)
    if img is None:
        print("Không đọc được ảnh:", path)
        sys.exit(1)
    print(f"[ok] Đọc ảnh {path}  ({img.shape[1]}x{img.shape[0]})")
else:
    if mss is None:
        print("Chưa cài mss để chụp live:  pip install mss")
        sys.exit(1)
    print("[..] Chụp live màn hình chính...")
    img = det.capture()

res = det.detect(img)
det.debug_dump("debug", img)

print("\n=== KẾT QUẢ ===")
for slot in (0, 1):
    r = res[slot]
    print(f"Ô súng {slot+1}: OCR='{r['text']}'  ->  {r['weapon_id']}  (score {r['score']})")
print("inventory_open:", res["inventory_open"])
print("\nĐã lưu ./debug/full_boxes.png — mở xem 2 khung vàng có trùm đúng tên súng không.")
