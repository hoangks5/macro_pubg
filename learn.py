# -*- coding: utf-8 -*-
"""
Công cụ HỌC ICON phụ kiện -> lưu vào thư viện templates/<category>/<attid>.png

Lệnh:
  # Xem các ô phụ kiện của 1 súng (scope + hàng dưới) -> lưu montage
  python learn.py show 1                 (live, súng ô 1)
  python learn.py show 2 shot.png        (từ ảnh, súng ô 2)

  # Lưu 1 icon làm mẫu:  <wslot 1|2> <pos> <category> <attid> [image]
  # pos: 1=scope, 2=muzzle, 3=grip, 4=mag, 5=stock
  python learn.py save 1 1 scope 4x shot.png
  python learn.py save 1 2 muzzle comp_ar shot.png     # AUG (AR) -> Compensator AR
  python learn.py save 1 3 grip   vertical shot.png
  python learn.py save 2 2 muzzle comp_smg shot.png    # nếu là súng SMG
  python learn.py save 1 4 mag    extended shot.png

  # TỰ CẮT phụ kiện CHƯA nhận diện được -> lưu vào thư mục draft/
  python learn.py draft                 (live)
  python learn.py draft shot.png        (từ ảnh)
  # -> mở draft/ xem, đổi tên file thành <category>__<attid>.png rồi chạy:
  python learn.py import                (đẩy hết draft/ đã đặt tên vào templates/)

  # Liệt kê template đã có
  python learn.py list

category: scope | muzzle | grip | stock | mag
attid: PHẢI trùng id trong backend/weapons.py.
  scope : red_dot, holo, 2x, 3x, 4x, 6x, 8x, 15x
  muzzle: comp_ar, muzzle_brake_ar, flash_ar, supp_ar,
          comp_smg, flash_smg, supp_smg,
          comp_sr, flash_sr, supp_sr
  grip  : vertical, half, thumb, angled, light, laser
  stock : tactical, cheek, bullet_loops, uzi_stock
  mag   : extended, quickdraw, ext_quick
LƯU Ý: họng súng (muzzle) khác icon giữa AR / SMG / Sniper -> phải lưu mẫu
RIÊNG cho từng nhóm (comp_ar khác comp_smg).
Vị trí ô (pos): 1=scope (ô trên thân súng), 2..5 là hàng dưới.

BIẾN THỂ (cùng phụ kiện nhưng icon khác giữa các súng, vd mag 5.56 thẳng vs
7.62 cong): thêm hậu tố '@tên' vào attid, KHÔNG đè mẫu cũ. Ví dụ:
  python learn.py save 2 4 mag    ext_quick@m762 shot.png
  python learn.py save 2 2 muzzle comp_ar@m762   shot.png
Phần trước '@' là id thật; phần sau chỉ để phân biệt biến thể.
"""

import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
from backend.vision import WeaponDetector, ATTACH_SLOTS, ATTACH_CATS, TEMPLATE_DIR
from backend.attach_matcher import BOX_CATEGORIES

BASE = os.path.dirname(os.path.abspath(__file__))
SHOT = os.path.join(BASE, "shot.png")


def load_image(arg_path):
    if arg_path:
        img = cv2.imread(arg_path)
        if img is None:
            print("Không đọc được ảnh:", arg_path)
            sys.exit(1)
        return img
    det = WeaponDetector()
    return det.capture()


def cmd_show(wslot, image):
    img = load_image(image)
    boxes = ATTACH_SLOTS[wslot - 1]
    os.makedirs("debug", exist_ok=True)
    for i, (x, y, w, h) in enumerate(boxes, 1):
        crop = img[y:y + h, x:x + w]
        cv2.imwrite(os.path.join("debug", f"slot{wslot}_pos{i}.png"), crop)
    print(f"Đã lưu {len(boxes)} ô của súng {wslot} vào debug/slot{wslot}_pos*.png")
    print("Mở xem để biết vị trí nào gắn phụ kiện gì, rồi dùng lệnh save.")


def cmd_save(wslot, pos, cat, attid, image):
    if cat not in ATTACH_CATS:
        print("category phải là:", ATTACH_CATS); sys.exit(1)
    img = load_image(image)
    x, y, w, h = ATTACH_SLOTS[wslot - 1][pos - 1]
    crop = img[y:y + h, x:x + w]
    out_dir = os.path.join(TEMPLATE_DIR, cat)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{attid}.png")
    cv2.imwrite(out, crop)
    print(f"Đã lưu mẫu: {out}  (từ súng {wslot}, ô {pos})")


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", (s or "").strip().lower()).strip("_")


def cmd_draft(image):
    """Quét 2 ô súng. Ô nào CÓ phụ kiện nhưng KHÔNG khớp template (chưa nhận
    diện được) thì cắt icon ra và lưu vào draft/ để bạn tự đặt tên."""
    det = WeaponDetector()
    img = load_image(image)
    draft_dir = os.path.join(BASE, "draft")
    os.makedirs(draft_dir, exist_ok=True)

    # tên nguồn (để nhiều ảnh khác nhau không ghi đè nhau)
    if image:
        src = os.path.splitext(os.path.basename(image))[0]
    else:
        import time
        src = time.strftime("live%H%M%S")

    labels = det.BOX_LABELS  # ["scope","muzzle","grip","stock"]
    saved = 0
    for wslot in (1, 2):
        boxes = det.attach_slots.get(wslot - 1, [])
        for idx, box in enumerate(boxes):
            x, y, w, h = box
            crop = img[y:y + h, x:x + w]
            posname = labels[idx] if idx < len(labels) else f"pos{idx + 1}"

            # bỏ ô trống (gần như đồng màu)
            if cv2 is not None:
                gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                if det._is_empty_slot(gray):
                    print(f"  súng {wslot} ô {posname}: TRỐNG -> bỏ qua")
                    continue

            # đoán thử + lấy điểm khớp (templates rỗng -> none/0)
            expected_cat = BOX_CATEGORIES[idx] if idx < len(BOX_CATEGORIES) else None
            if expected_cat == "scope":
                attid, score = det._match_scope(img, box)
                cat = "scope"
                passed = bool(attid) and score >= det.thresholds.get("scope", 0.66)
            elif expected_cat:
                cat, attid, score = det._match_icon(
                    crop, expected_cat=expected_cat, apply_threshold=False)
                passed = bool(attid) and score >= det.thresholds.get(cat or "", 0.58)
            else:
                continue

            # đã nhận diện chắc chắn -> không cần lưu draft
            if passed:
                print(f"  súng {wslot} ô {posname}: đã nhận = {attid} ({score:.2f}) -> bỏ qua")
                continue

            fname = f"{src}__w{wslot}_{posname}_{score:.2f}.png"
            out = os.path.join(draft_dir, fname)
            cv2.imwrite(out, crop)
            saved += 1
            print(f"  CẮT: súng {wslot} ô {posname} -> draft/{fname}")

    print(f"\nĐã lưu {saved} icon chưa nhận diện vào: {draft_dir}")
    if saved:
        print("Bước tiếp theo: mở thư mục draft/, ĐỔI TÊN từng file thành")
        print("  <category>__<attid>.png   ví dụ:  scope__red_dot.png , muzzle__comp_ar.png")
        print("(category: scope|muzzle|grip|stock|mag ; attid xem trong backend/weapons.py)")
        print("Đặt tên xong chạy:  python learn.py import")


def cmd_import():
    """Đẩy các file trong draft/ ĐÃ đặt tên dạng <category>__<attid>.png vào
    thư viện templates/<category>/<attid>.png."""
    draft_dir = os.path.join(BASE, "draft")
    if not os.path.isdir(draft_dir):
        print("Chưa có thư mục draft/. Chạy 'python learn.py draft' trước."); return
    moved = skipped = 0
    for fn in sorted(os.listdir(draft_dir)):
        if not fn.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        stem, ext = os.path.splitext(fn)
        if "__" not in stem:
            print(f"  BỎ QUA (chưa đặt tên đúng dạng category__attid): {fn}")
            skipped += 1
            continue
        cat_raw, attid_raw = stem.split("__", 1)
        cat = _slug(cat_raw)
        if cat not in ATTACH_CATS:
            print(f"  BỎ QUA (category '{cat}' không hợp lệ): {fn}")
            skipped += 1
            continue
        attid = attid_raw.strip()  # giữ nguyên (cho phép hậu tố @bienthe)
        out_dir = os.path.join(TEMPLATE_DIR, cat)
        os.makedirs(out_dir, exist_ok=True)
        src = os.path.join(draft_dir, fn)
        dst = os.path.join(out_dir, f"{attid}{ext.lower()}")
        img = cv2.imread(src)
        if img is None:
            print(f"  LỖI đọc ảnh: {fn}"); skipped += 1; continue
        cv2.imwrite(dst, img)
        os.remove(src)
        moved += 1
        print(f"  + templates/{cat}/{attid}{ext.lower()}")
    print(f"\nĐã nhập {moved} template, bỏ qua {skipped}.")
    if moved:
        cmd_list()


def cmd_list():
    det = WeaponDetector()
    cnt = det.template_count()
    print("Thư viện mẫu hiện có:")
    for cat in ATTACH_CATS:
        d = os.path.join(TEMPLATE_DIR, cat)
        items = [os.path.splitext(f)[0] for f in os.listdir(d)] if os.path.isdir(d) else []
        print(f"  {cat:7}: {cnt[cat]:2d}  {items}")


def main():
    a = sys.argv[1:]
    if not a:
        print(__doc__); return
    if a[0] == "list":
        cmd_list()
    elif a[0] == "draft":
        image = a[1] if len(a) > 1 else None
        cmd_draft(image)
    elif a[0] == "import":
        cmd_import()
    elif a[0] == "show":
        wslot = int(a[1]) if len(a) > 1 else 1
        image = a[2] if len(a) > 2 else None
        cmd_show(wslot, image)
    elif a[0] == "save":
        if len(a) < 5:
            print("Thiếu tham số. Xem: python learn.py"); return
        wslot, pos, cat, attid = int(a[1]), int(a[2]), a[3], a[4]
        image = a[5] if len(a) > 5 else None
        cmd_save(wslot, pos, cat, attid, image)
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
