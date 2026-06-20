# -*- coding: utf-8 -*-
"""
Nhận diện SÚNG từ màn hình inventory PUBG bằng OCR (giai đoạn 1).

Pipeline:
  1) Chụp màn hình (mss) — hoặc nhận 1 ảnh có sẵn.
  2) Cắt vùng tên súng của Ô 1 / Ô 2 (toạ độ cố định ở 1920x1080).
  3) Tiền xử lý ảnh (xám -> phóng to -> nhị phân) cho dễ đọc.
  4) OCR bằng Tesseract -> chuỗi text.
  5) So khớp mờ (fuzzy) với danh sách tên súng -> ra weapon_id.

"Inventory đang mở?" được suy ra luôn từ kết quả: nếu đọc được ít nhất 1 tên
súng khớp đủ điểm thì coi như balo đang hiển thị (không cần template riêng).

Toạ độ vùng cắt là GIÁ TRỊ TẠM cho 1920x1080 — cần hiệu chỉnh bằng calibrate.py.
"""

import os
import re
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

try:
    import numpy as np
except Exception:
    np = None

try:
    import cv2
except Exception:
    cv2 = None

try:
    import mss
except Exception:
    mss = None

try:
    import pytesseract
except Exception:
    pytesseract = None

from . import weapons
from .attach_matcher import AttachMatcher, BOX_CATEGORIES, LOWER_CATEGORIES, MUZZLE_ATTID_TO_FAMILY
from .scope_matcher import ScopeMatcher, SCOPE_SCAN_PAD_X, SCOPE_SCAN_PAD_Y
from .scope_matcher import SCOPE_MATCH_FLOOR, SCOPE_MATCH_MARGIN
from . import match_utils as mu

# Vùng cắt tên súng [x, y, w, h] — đã căn theo ảnh inventory 1920x1080 của bạn
# (Ô1 = AUG, Ô2 = Beryl M762). Panel súng neo theo góc TRÊN-PHẢI màn hình.
DEFAULT_REGIONS = {
    "slot1_name": [1366, 90, 222, 42],
    "slot2_name": [1366, 314, 222, 42],
}

# Vị trí các ô phụ kiện [x, y, w, h] — 1920x1080.
# Mỗi ô súng gồm:
#   - scope: ô nhỏ phía TRÊN thân súng
#   - muzzle/grip/mag/stock: hàng icon phía dưới
ATTACH_SLOTS = {
    # scope | muzzle | grip | stock  (bỏ ô mag — không ảnh hưởng độ giật)
    # w/h thu 3px từ phải-dưới (x,y giữ nguyên)
    0: [[1599, 101, 51, 51], [1335, 244, 51, 51], [1436, 244, 51, 51], [1761, 244, 51, 51]],
    1: [[1599, 324, 51, 51], [1335, 466, 51, 51], [1436, 466, 51, 51], [1761, 466, 51, 51]],
}

# Thư mục thư viện ảnh mẫu icon phụ kiện: templates/<category>/<attid>.png
TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates"
)
# Icon chưa nhận diện được -> draft/ (đặt tên thủ công bằng learn.py import)
DRAFT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "draft"
)
ATTACH_CATS = ("scope", "muzzle", "grip", "stock", "mag")

# Ngưỡng khớp icon theo TỪNG loại phụ kiện (0..1, càng cao càng chặt).
# scope cao hơn vì nó nằm TRÊN mô hình 3D súng -> nền thay đổi theo súng/skin,
# rất dễ nhiễu; thà bỏ sót (none) còn hơn nhận SAI scope.
DEFAULT_THRESHOLDS = {
    "scope": 0.52,
    "muzzle": 0.52,
    "grip": 0.58,
    "stock": 0.58,
    "mag": 0.58,
}
# Khi điểm chưa đạt ngưỡng nhưng ứng viên #1 vượt trội #2 -> vẫn chấp nhận
# (giảm false-negative do nền ô khác màu giữa các súng).
MATCH_MARGIN = mu.MATCH_MARGIN
MATCH_FLOOR = mu.MATCH_FLOOR

# Map họ họng -> attid theo loại súng (SAU khi nhận diện icon theo họ).
WEAPON_MUZZLE_FAMILY_ID = {
    "AR": {
        "comp": "comp_ar", "flash": "flash_ar", "supp": "supp_ar",
        "brake": "muzzle_brake_ar",
    },
    "SMG": {
        "comp": "comp_smg", "flash": "flash_smg", "supp": "supp_smg",
    },
    "DMR": {
        "comp": "comp_sr", "flash": "flash_sr", "supp": "supp_sr",
        "brake": "muzzle_brake_ar",
    },
    "SR": {
        "comp": "comp_sr", "flash": "flash_sr", "supp": "supp_sr",
    },
    "LMG": {
        "comp": "comp_ar", "flash": "flash_ar", "supp": "supp_ar",
        "brake": "muzzle_brake_ar",
    },
    "PISTOL": {
        "comp": "comp_smg", "flash": "flash_smg", "supp": "supp_smg",
    },
}

# Giữ tương thích cũ (main.py migrate) — không dùng khi nhận diện.
MUZZLE_ID_FOR_WEAPON = {
    "AR": {},
    "SMG": {"supp_ar": "supp_smg", "comp_ar": "comp_smg", "flash_ar": "flash_smg"},
    "DMR": {
        "supp_ar": "supp_sr", "comp_ar": "comp_sr", "flash_ar": "flash_sr",
        "supp_sr": "supp_sr", "comp_sr": "comp_sr", "flash_sr": "flash_sr",
        "muzzle_brake_ar": "muzzle_brake_ar",
    },
    "LMG": {},
    "PISTOL": {},
}

# --- Map THƯ MỤC template -> category nội bộ ---------------------------------
# Bộ icon CHÍNH THỨC của PUBG đặt theo tên thư mục trong game; ánh xạ về
# category nội bộ (scope/muzzle/grip/stock/mag). Hỗ trợ cả tên cũ.
FOLDER_TO_CAT = {
    "upper rail": "scope", "scope": "scope",
    "muzzle": "muzzle",
    "lower rail": "grip", "grip": "grip",
    "magazine": "mag", "mag": "mag",
    "stocks": "stock", "stock": "stock",
}

# --- Map TÊN FILE (đã hạ chữ thường) -> attid trong weapons.py ----------------
NAME_TO_ATTID = {
    "scope": {
        "red dot": "red_dot", "red dot sight": "red_dot",
        "holo": "holo", "holographic": "holo",
        "2x": "2x", "3x": "3x", "4x": "4x", "6x": "6x", "8x": "8x", "15x": "15x",
    },
    "muzzle": {
        "compensator (ar, dmr, s12k)": "comp_ar",
        "compensator (smg)": "comp_smg",
        "compensator (dmr, sr)": "comp_sr",
        "muzzle brake (ar, dmr, o12, s12k)": "muzzle_brake_ar",
        "muzzle brake": "muzzle_brake_ar",
        "flash hider (ar, dmr, s12k)": "flash_ar",
        "flash hider (smg)": "flash_smg",
        "flash hider (dmr, sr)": "flash_sr",
        "suppressor (ar, dmr, s12k)": "supp_ar",
        "suppressor (handgun, smg)": "supp_smg",
        "suppressor (dmr, sr)": "supp_sr",
    },
    "grip": {
        "angled foregrip (ar, smg, dmr)": "angled", "angled foregrip": "angled",
        "half grip": "half", "light grip": "light", "thumb grip": "thumb",
        "vertical foregrip": "vertical", "vertical grip": "vertical",
        "laser sight": "laser",
    },
    "stock": {
        "tactical stock": "tactical", "cheek pad": "cheek",
        "bullet loops": "bullet_loops",
        "stock for micro uzi": "uzi_stock", "stock micro uzi": "uzi_stock",
    },
    "mag": {
        "extended mag": "extended", "extended quickdraw mag": "ext_quick",
        "quickdraw mag": "quickdraw",
    },
}


def _attid_from_filename(cat, stem):
    """Suy ra attid từ tên file. Ưu tiên bảng map; nếu không có thì thử bỏ phần
    '(...)', cuối cùng slug hoá (khoảng trắng -> '_')."""
    key = stem.strip().lower()
    table = NAME_TO_ATTID.get(cat, {})
    if key in table:
        return table[key]
    base = re.sub(r"\s*\(.*?\)\s*", "", key).strip()   # bỏ phần trong ngoặc
    if base in table:
        return table[base]
    return re.sub(r"[^a-z0-9]+", "_", base).strip("_")  # slug dự phòng

# Nếu Tesseract không nằm trong PATH, để đường dẫn .exe ở đây
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

_OCR_CFG = (
    "--psm 7 -c tessedit_char_whitelist="
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789- "
)

# Ngưỡng khớp tên súng — cao hơn để tránh nhận sai; #2 phải thua #1 rõ ràng.
WEAPON_MATCH_THRESHOLD = 0.68
WEAPON_MATCH_MARGIN = 0.10


def _clean(s):
    return re.sub(r"[^A-Z0-9 ]", "", (s or "").upper()).strip()


# OCR inventory PUBG hay đọc sai — sửa trước khi so khớp tên súng.
_WEAPON_OCR_FIX = {
    "MIBA4": "M16A4",
    "M1BA4": "M16A4",
    "MIGA4": "M16A4",
    "M1IA4": "M16A4",
    "MIIA4": "M16A4",
    "M1GA4": "M16A4",
    "MIOA4": "M16A4",
}


def _normalize_weapon_ocr(text):
    """Chuẩn hoá text OCR: bỏ số ô balo, sửa lỗi hay gặp (MIBA4 -> M16A4)."""
    t = _clean(text)
    if not t:
        return ""
    t = re.sub(r"^\d+\s*[-]?\s*", "", t).strip()
    t_ns = t.replace(" ", "")
    if t_ns in _WEAPON_OCR_FIX:
        return _WEAPON_OCR_FIX[t_ns]
    if re.match(r"^MI?[BGI]A4$", t_ns):
        return "M16A4"
    return t


def normalize_muzzle_attid(attid, weapon):
    """Map attid họng (sau nhận diện icon) -> id đúng theo loại súng."""
    if not attid or attid == "none" or weapon is None:
        return attid
    fam = MUZZLE_ATTID_TO_FAMILY.get(attid)
    if not fam:
        return attid
    wtype = weapon.get("type", "AR")
    mapping = WEAPON_MUZZLE_FAMILY_ID.get(wtype, WEAPON_MUZZLE_FAMILY_ID["AR"])
    return mapping.get(fam, attid)


class WeaponDetector:
    def __init__(self, regions=None, tesseract_path=None, thresholds=None,
                 attach_slots=None, auto_draft=True):
        self.regions = dict(regions or DEFAULT_REGIONS)
        # vị trí ô phụ kiện (có thể chỉnh từ editor F10 / config.json)
        self.attach_slots = self._coerce_slots(attach_slots or ATTACH_SLOTS)
        # Tự cắt icon chưa nhận diện -> draft/ (không ghi vào templates/)
        self.auto_draft = bool(auto_draft)
        self._draft_seen = set()
        self._draft_count = 0
        self.draft_limit = 300
        # ngưỡng khớp theo loại phụ kiện (có thể chỉnh từ config.json)
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.set_thresholds(thresholds)
        # id -> tên đã chuẩn hoá để so khớp
        self.names = {w["id"]: _clean(w["name"]) for w in weapons.WEAPONS}
        # Token OCR hay nhầm / tên viết tắt trong game
        self.alias_tokens = {
            "m416": ["M416", "M4I6", "M4IF", "M4IG", "M41G", "M4I6"],
            "akm": ["AKM"],
            "scarl": ["SCARL", "SCAR-L"],
            "m16a4": ["M16A4", "M16", "M1GA4", "M1BA4", "M164", "M16A",
                       "MIBA4", "MIGA4", "M1IA4"],
            "m762": ["M762", "M76Z", "BERYL", "BERYLM762"],
            "g36c": ["G36C", "G36"],
            "aug": ["AUG", "AUGA3"],
            "qbz": ["QBZ95", "QBZ"],
            "mk47": ["MK47", "MUTANT"],
            "groza": ["GROZA"],
            "k2": ["K2"],
            "ace32": ["ACE32"],
            "famas": ["FAMAS"],
            "ump45": ["UMP45"],
            "vector": ["VECTOR"],
            "tommy": ["TOMMY", "THOMPSON"],
            "mp5k": ["MP5K"],
            "pp19": ["PP19", "BIZON"],
            "p90": ["P90"],
            "uzi": ["MICROUZI"],
            "js9": ["JS9"],
            "m249": ["M249"],
            "dp28": ["DP28", "DP-28"],
            "mg3": ["MG3"],
            "mini14": ["MINI14"],
            "sks": ["SKS"],
            "slr": ["SLR"],
            "qbu": ["QBU"],
            "mk12": ["MK12", "MK1Z", "MKIZ", "MKI2", "M712", "M7Z2", "M7G2"],
            "mk14": ["MK14"],
            "vss": ["VSS"],
            "dragunov": ["DRAGUNOV"],
            "m24": ["M24"],
            "awm": ["AWM"],
            "win94": ["WIN94", "WIN-94"],
            "lynx_amr": ["LYNXAMR", "LYNX", "LYNX AMR"],
            "p18c": ["P18C"],
            "skorpion": ["SKORPION"],
        }
        # chế độ TEST: nếu set đường dẫn ảnh -> đọc ảnh này thay vì chụp màn hình
        self.debug_image = None
        self.templates = {c: {} for c in ATTACH_CATS}  # cat -> {attid: gray img}
        self.attach_matcher = None
        self.scope_matcher = None
        self.load_templates()
        if pytesseract:
            path = tesseract_path or TESSERACT_PATH
            if path and os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path

    @staticmethod
    def _coerce_slots(d):
        """Chuẩn hoá dict ô phụ kiện: {0:[[x,y,w,h],...], 1:[...]} với key int."""
        out = {}
        for k, v in (d or {}).items():
            out[int(k)] = [[int(n) for n in box] for box in v]
        return out

    def set_attach_slots(self, d):
        if d:
            self.attach_slots = self._coerce_slots(d)
        return self.attach_slots

    # ---------- chuẩn hoá 1 ảnh template (alpha -> nền đen + cắt sát icon) ----
    @staticmethod
    def _load_template_gray(path):
        """Đọc template xám.
        - Icon CHÍNH THỨC (PNG alpha): tách nền + cắt sát icon.
        - Crop inventory game (~50x50, có nền): GIỮ NGUYÊN khung để khớp direct."""
        im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if im is None:
            return None
        if im.ndim == 3 and im.shape[2] == 4:
            return WeaponDetector._prep_template_file(path)
        if im.ndim == 2:
            gray = im
        else:
            gray = cv2.cvtColor(im[:, :, :3], cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        if h <= 64 and w <= 64:
            return gray
        return WeaponDetector._isolate_icon(gray)

    @staticmethod
    def _prep_template_file(path):
        """Đọc icon CHÍNH THỨC (PNG có alpha, nền trong suốt).
        - Ghép icon lên nền ĐEN (giống ô phụ kiện trong game có nền tối).
        - Cắt sát theo viền alpha -> chỉ giữ phần icon (đồng cỡ với icon trong ô).
        Trả ảnh xám uint8, hoặc None."""
        im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if im is None:
            return None
        if im.ndim == 2:                       # đã là xám
            return WeaponDetector._isolate_icon(im)
        if im.shape[2] == 4:
            bgr = im[:, :, :3].astype("float32")
            a = (im[:, :, 3].astype("float32") / 255.0)[:, :, None]
            comp = (bgr * a).astype("uint8")   # nền trong suốt -> đen
            gray = cv2.cvtColor(comp, cv2.COLOR_BGR2GRAY)
            mask = im[:, :, 3]
            ys, xs = np.where(mask > 16) if np is not None else (None, None)
            if ys is not None and len(ys) and len(xs):
                y0, y1 = ys.min(), ys.max() + 1
                x0, x1 = xs.min(), xs.max() + 1
                gray = gray[y0:y1, x0:x1]
            return WeaponDetector._isolate_icon(gray)
        gray = cv2.cvtColor(im, cv2.COLOR_BGR2GRAY)
        return WeaponDetector._isolate_icon(gray)

    # ---------- thư viện ảnh mẫu phụ kiện ----------
    def load_templates(self):
        """templates[cat] = {attid: [ảnh xám, ...]}.
        Đọc bộ icon CHÍNH THỨC theo cấu trúc thư mục PUBG (Upper Rail / Muzzle /
        Lower Rail / Magazine / Stock). Tên file -> attid qua NAME_TO_ATTID.
        Vẫn hỗ trợ NHIỀU biến thể: thêm hậu tố '@tên' vào tên file (phần trước
        '@' dùng để suy ra attid, phần sau chỉ để phân biệt)."""
        self.templates = {c: {} for c in ATTACH_CATS}
        if cv2 is None or not os.path.isdir(TEMPLATE_DIR):
            return self.templates
        for entry in os.listdir(TEMPLATE_DIR):
            d = os.path.join(TEMPLATE_DIR, entry)
            if not os.path.isdir(d):
                continue
            cat = FOLDER_TO_CAT.get(entry.strip().lower())
            if cat is None:
                continue
            for fn in os.listdir(d):
                if not fn.lower().endswith((".png", ".jpg", ".jpeg")):
                    continue
                # Bỏ qua mẫu tự học cũ (@auto_*) — dễ gán sai attid, làm nhận diện lệch.
                if "@auto" in fn.lower():
                    continue
                stem = os.path.splitext(fn)[0].split("@")[0]
                attid = _attid_from_filename(cat, stem)
                img = self._load_template_gray(os.path.join(d, fn))
                if img is not None and img.size:
                    self.templates[cat].setdefault(attid, []).append(img)
        self._refresh_matchers()
        self._supplement_scope_from_drafts()
        self._refresh_matchers()
        return self.templates

    @staticmethod
    def _template_dhash(gray):
        s = cv2.resize(gray, (12, 12), interpolation=cv2.INTER_AREA)
        bits = (s > s.mean()).astype("uint8").flatten()
        return "".join(str(b) for b in bits)

    def _supplement_scope_from_drafts(self, max_per_attid=6):
        """Bổ sung mẫu scope từ draft/ — crop inventory thật, nền/skin đa dạng."""
        if cv2 is None or not os.path.isdir(DRAFT_DIR) or not self.scope_matcher:
            return
        box = [0, 0, 50, 50]
        counts = {}
        seen = set()
        candidates = []
        for fn in os.listdir(DRAFT_DIR):
            if "__scope__" not in fn or not fn.lower().endswith(".png"):
                continue
            path = os.path.join(DRAFT_DIR, fn)
            img = cv2.imread(path)
            if img is None or img.size == 0:
                continue
            ranked = self.scope_matcher.match_ranked(img, box, None)
            if not ranked:
                continue
            attid, score = ranked[0]
            second = ranked[1][1] if len(ranked) > 1 else 0.0
            margin = score - second
            if attid == "none" or score < SCOPE_MATCH_FLOOR or margin < SCOPE_MATCH_MARGIN:
                continue
            g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            if g.shape[0] > 64 or g.shape[1] > 64:
                g = cv2.resize(g, (50, 50), interpolation=cv2.INTER_AREA)
            candidates.append((attid, margin, score, fn, g))
        candidates.sort(key=lambda x: (-x[1], -x[2]))
        for attid, margin, score, fn, g in candidates:
            if counts.get(attid, 0) >= max_per_attid:
                continue
            h = self._template_dhash(g)
            if h in seen:
                continue
            seen.add(h)
            self.templates["scope"].setdefault(attid, []).append(g)
            counts[attid] = counts.get(attid, 0) + 1

    def _refresh_matchers(self):
        """Cập nhật bộ khớp sau khi load/đổi template hoặc ngưỡng."""
        self.attach_matcher = AttachMatcher(self.templates, self.thresholds)
        self.scope_matcher = ScopeMatcher(
            self.templates, self.thresholds.get("scope", 0.52))

    def template_count(self):
        return {c: sum(len(v) for v in d.values()) for c, d in self.templates.items()}

    def set_thresholds(self, thresholds):
        """Cập nhật ngưỡng khớp theo loại phụ kiện (giữ nguyên các loại không nêu)."""
        if not thresholds:
            return self.thresholds
        for cat, val in thresholds.items():
            if cat in self.thresholds:
                try:
                    self.thresholds[cat] = max(0.0, min(1.0, float(val)))
                except (TypeError, ValueError):
                    pass
        if self.attach_matcher:
            self.attach_matcher.set_thresholds(self.thresholds)
        if self.scope_matcher:
            self.scope_matcher.set_threshold(self.thresholds.get("scope", 0.52))
        return self.thresholds

    # ---------- chụp màn hình (hoặc đọc ảnh test) ----------
    def capture(self):
        if self.debug_image and cv2 is not None and os.path.exists(self.debug_image):
            img = cv2.imread(self.debug_image)
            if img is not None:
                return img
        if not mss:
            raise RuntimeError("Chưa cài 'mss' (pip install mss)")
        with mss.mss() as sct:
            mon = sct.monitors[1]            # màn hình chính
            shot = sct.grab(mon)
        img = np.array(shot)                 # BGRA
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    # ---------- OCR 1 vùng ----------
    def _ocr_variants(self, gray, gray_eq):
        """Sinh ảnh nhị phân cho OCR — ít variant, ưu tiên chữ trắng inventory PUBG."""
        seen = set()

        def _yield_unique(img):
            key = img.tobytes()
            if key not in seen:
                seen.add(key)
                yield img

        for g in (gray, gray_eq):
            bright = ((g > 165).astype("uint8") * 255)
            k = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            bright = cv2.morphologyEx(bright, cv2.MORPH_CLOSE, k, iterations=1)
            for img in _yield_unique(255 - bright):
                yield img
            for thr in (170, 180, 190):
                _, th = cv2.threshold(g, thr, 255, cv2.THRESH_BINARY)
                for img in _yield_unique(255 - th):
                    yield img
            _, th_inv = cv2.threshold(g, 145, 255, cv2.THRESH_BINARY_INV)
            for img in _yield_unique(th_inv):
                yield img

    def _ocr(self, crop):
        if not pytesseract or crop is None or crop.size == 0:
            return ""
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray_eq = clahe.apply(gray)

        def _read(th):
            x = cv2.copyMakeBorder(
                th, 14, 14, 14, 14, cv2.BORDER_CONSTANT, value=255)
            try:
                return pytesseract.image_to_string(x, config=_OCR_CFG).strip()
            except Exception:
                return ""

        best_txt, best_score = "", 0.0
        good_enough = WEAPON_MATCH_THRESHOLD
        for th in self._ocr_variants(gray, gray_eq):
            raw = _read(th)
            txt = _normalize_weapon_ocr(raw)
            if not txt:
                continue
            ranked = self.match_ranked(txt)
            if not ranked:
                continue
            score = ranked[0][1]
            second = ranked[1][1] if len(ranked) > 1 else 0.0
            if score > best_score:
                best_txt, best_score = txt, score
            # Đủ tin cậy -> dừng sớm, tránh gọi Tesseract thêm
            if score >= 0.92:
                break
            if score >= good_enough and (score - second) >= WEAPON_MATCH_MARGIN:
                break
        return best_txt

    # ---------- so khớp tên ----------
    @staticmethod
    def _alias_score(t_ns, aliases):
        """Điểm alias: khớp chính xác > substring dài; tránh M24 dính M249."""
        best = 0.0
        for tok in aliases:
            tok_ns = re.sub(r"[^A-Z0-9]", "", (tok or "").upper())
            if not tok_ns:
                continue
            if t_ns == tok_ns:
                return 1.0
            if len(tok_ns) >= 5 and tok_ns in t_ns:
                best = max(best, 0.93)
        return best

    @staticmethod
    def _near_name_penalty(t_ns, n_ns, score):
        """Giảm điểm khi OCR và tên súng gần giống nhưng khác 1–2 ký tự (M24/M249)."""
        if n_ns == t_ns or score <= 0:
            return score
        if (n_ns.startswith(t_ns) or t_ns.startswith(n_ns)):
            if 0 < abs(len(n_ns) - len(t_ns)) <= 2:
                return score * 0.72
        return score

    @staticmethod
    def _disambig_m762_mk12(t_ns, ranked, raw_t=""):
        """Mk12 hay bị OCR thành M762/M7Z2; Beryl thường có thêm 'Beryl' trong vùng tên."""
        ambiguous = {"M762", "M76Z", "M7Z2", "M7G2", "M712"}
        if t_ns not in ambiguous or "BERYL" in t_ns:
            return ranked
        # "M76 2" / "M7 62" có khoảng trắng -> thường là Beryl M762 thật
        if raw_t and re.search(r"M76\s+2|M7\s+62", raw_t, re.I):
            return ranked
        scores = {wid: sc for wid, sc in ranked}
        mk = scores.get("mk12", 0.0)
        m7 = scores.get("m762", 0.0)
        if t_ns in ("M7Z2", "M7G2", "M712"):
            scores["mk12"] = max(mk, 0.96)
            scores["m762"] = min(m7, 0.55)
        else:
            # M762 / M76Z: 4 ký tự, không có Beryl -> ưu tiên Mk12
            scores["mk12"] = max(mk, 0.94)
            scores["m762"] = min(m7, 0.68)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    @staticmethod
    def _disambig_m16_m416(t_ns, ranked):
        """OCR hay đọc 'M16A4' thành 'M16' — đó là M16A4, không phải M416."""
        if t_ns != "M16":
            return ranked
        scores = {wid: sc for wid, sc in ranked}
        scores["m16a4"] = max(scores.get("m16a4", 0), 1.0)
        scores["m416"] = min(scores.get("m416", 0), 0.60)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)

    def match_ranked(self, text):
        """Trả [(weapon_id, score), ...] theo điểm giảm dần."""
        raw_t = _clean(text)
        t = _normalize_weapon_ocr(text)
        if not t:
            return []
        t_ns = t.replace(" ", "")
        ranked = []
        for wid, name in self.names.items():
            n_ns = name.replace(" ", "")
            s = SequenceMatcher(None, t_ns, n_ns).ratio()
            if t_ns == n_ns:
                s = 1.0
            alias_s = self._alias_score(t_ns, self.alias_tokens.get(wid, []))
            s = max(s, alias_s)
            # Không phạt prefix khi alias khớp chính xác (vd M16 -> M16A4)
            if alias_s < 1.0:
                s = self._near_name_penalty(t_ns, n_ns, s)
            for tok in name.split():
                tk = re.sub(r"[^A-Z0-9]", "", tok.upper())
                if len(tk) >= 5 and tk in t_ns:
                    s = max(s, min(1.0, s + 0.08))
            ranked.append((wid, min(s, 1.0)))
        ranked.sort(key=lambda x: x[1], reverse=True)
        ranked = self._disambig_m762_mk12(t_ns, ranked, raw_t=t)
        ranked = self._disambig_m16_m416(t_ns, ranked)
        return ranked

    def match(self, text, threshold=None, margin=None):
        ranked = self.match_ranked(text)
        if not ranked:
            return None, 0.0
        best_id, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        thr = WEAPON_MATCH_THRESHOLD if threshold is None else threshold
        mg = WEAPON_MATCH_MARGIN if margin is None else margin
        if best_score < thr:
            return None, best_score
        if best_score - second_score < mg:
            return None, best_score
        return best_id, best_score

    # ---------- tiện ích khớp icon (ủy quyền sang attach_matcher / match_utils) ----
    @staticmethod
    def _is_empty_slot(gray, min_std=11.0):
        return mu.is_empty_slot(gray, min_std)

    @staticmethod
    def _isolate_icon(gray):
        return mu.isolate_icon(gray)

    @staticmethod
    def _norm_contrast(gray):
        return mu.norm_contrast(gray)

    @staticmethod
    def _prep(gray, size=64, trim=0.12):
        return mu.prep_icon(gray, size=size, trim=trim)

    @staticmethod
    def _silhouette(gray):
        return mu.silhouette(gray)

    @staticmethod
    def _edge(gray):
        return mu.edge(gray)

    def _passes_threshold(self, cat, score, ranked):
        """Đạt ngưỡng thường HOẶC ứng viên #1 vượt trội rõ so với #2."""
        if cat is None:
            return False
        thr = self.thresholds.get(cat, 0.60)
        scores = [r[2] for r in ranked] if ranked else []
        return mu.passes_threshold(thr, score, scores)

    def _match_icon_ranked(self, crop, allowed=None, categories=None, expected_cat=None,
                           group_muzzle_families=False):
        """Trả [(cat, attid, score), ...] — mặc định chỉ 1 category nếu expected_cat được chỉ định."""
        if expected_cat:
            allow_set = None if allowed is None else allowed.get(expected_cat, set())
            ranked = self.attach_matcher.match_ranked(
                crop, expected_cat, allow_set,
                group_muzzle_families=group_muzzle_families)
            return [(expected_cat, attid, sc) for attid, sc in ranked]
        cats = categories or LOWER_CATEGORIES
        out = []
        for cat in cats:
            allow_set = None if allowed is None else allowed.get(cat, set())
            for attid, sc in self.attach_matcher.match_ranked(
                    crop, cat, allow_set,
                    group_muzzle_families=group_muzzle_families and cat == "muzzle"):
                out.append((cat, attid, sc))
        out.sort(key=lambda x: x[2], reverse=True)
        return out

    def _match_icon(self, crop, allowed=None, categories=None, apply_threshold=True,
                    expected_cat=None, group_muzzle_families=False):
        """
        Trả (category, attid, score).
        expected_cat: khóa ô vào đúng loại (muzzle/grip/stock) — nên luôn truyền
        khi biết vị trí ô để tránh nhảy lung tung giữa các loại phụ kiện.
        group_muzzle_families: nhận diện họng theo HỌ (comp/flash/supp), không lọc súng.
        """
        if cv2 is None or crop is None or crop.size == 0:
            return None, None, 0.0
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if self._is_empty_slot(g) and apply_threshold:
            return None, None, 0.0
        if expected_cat:
            allow_set = None if allowed is None else allowed.get(expected_cat, set())
            return self.attach_matcher.match(
                crop, expected_cat, allow_set, apply_threshold=apply_threshold,
                group_muzzle_families=group_muzzle_families)
        cats = categories or LOWER_CATEGORIES
        ranked = self._match_icon_ranked(
            crop, allowed, cats, group_muzzle_families=group_muzzle_families)
        best = ranked[0] if ranked else (None, None, 0.0)
        cat = best[0]
        if apply_threshold and not self._passes_threshold(cat, best[2], ranked):
            return None, None, round(best[2], 3)
        return best[0], best[1], round(best[2], 3)

    def _match_scope_scores(self, img, box, allowed_ids=None):
        return self.scope_matcher.match_ranked(img, box, allowed_ids)

    def _match_scope(self, img, box, allowed_ids=None):
        return self.scope_matcher.match(img, box, allowed_ids)

    # ---------- TỰ CẮT icon chưa nhận diện -> draft/ ----------
    @staticmethod
    def _draft_hash(crop):
        """Hash thô của icon để tránh lưu trùng mỗi lần bấm Tab."""
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        s = cv2.resize(g, (12, 12), interpolation=cv2.INTER_AREA)
        bits = (s > s.mean()).astype("uint8").flatten()
        return "".join(str(b) for b in bits)

    def _save_draft(self, crop, weapon, posname, score):
        """Lưu icon chưa nhận diện vào draft/ — chỉ để xem/đặt tên thủ công sau."""
        if not self.auto_draft or cv2 is None or crop is None or crop.size == 0:
            return False
        if self._draft_count >= self.draft_limit:
            return False
        try:
            h = self._draft_hash(crop)
        except Exception:
            return False
        if h in self._draft_seen:
            return False
        self._draft_seen.add(h)
        wid = (weapon or {}).get("id") or "unk"
        try:
            os.makedirs(DRAFT_DIR, exist_ok=True)
            fname = f"{wid}__{posname}__s{score:.2f}__{h[:8]}.png"
            cv2.imwrite(os.path.join(DRAFT_DIR, fname), crop)
            self._draft_count += 1
            return True
        except Exception:
            return False

    # ---------- nhận diện phụ kiện của 1 ô súng ----------
    def detect_attachments(self, img, weapon_slot, weapon=None):
        """
        weapon: dict súng đã nhận diện — chỉ dùng để map họng -> attid đúng loại súng.
        Nhận diện icon phụ kiện TRƯỚC (không lọc template theo súng).
        """
        empty = {c: "none" for c in ATTACH_CATS}
        if weapon is None:
            return empty
        result = dict(empty)
        scores = {}

        def _save_unmatched(crop, posname, score):
            self._save_draft(crop, weapon, posname, score)

        boxes = self.attach_slots.get(weapon_slot, [])
        for idx, box in enumerate(boxes):
            expected_cat = BOX_CATEGORIES[idx] if idx < len(BOX_CATEGORIES) else None
            if expected_cat is None:
                continue
            if not weapons.slot_enabled(weapon, expected_cat):
                continue
            posname = expected_cat
            if expected_cat == "scope":
                scope_ranked = self._match_scope_scores(img, box, None)
                if scope_ranked:
                    attid, score = scope_ranked[0]
                    second = scope_ranked[1][1] if len(scope_ranked) > 1 else 0.0
                    sr = [("scope", attid, score), ("scope", None, second)]
                    if self._passes_threshold("scope", score, sr):
                        result["scope"] = attid
                        scores["scope"] = score
                    else:
                        x, y, w, h = box
                        _save_unmatched(img[y:y + h, x:x + w], "scope", score)
                else:
                    x, y, w, h = box
                    _save_unmatched(img[y:y + h, x:x + w], "scope", 0.0)
                continue

            x, y, w, h = box
            crop = img[y:y + h, x:x + w]
            by_family = expected_cat == "muzzle"
            cat, attid, score = self._match_icon(
                crop, allowed=None, expected_cat=expected_cat,
                group_muzzle_families=by_family)
            if attid and by_family:
                attid = normalize_muzzle_attid(attid, weapon)
            if attid:
                result[expected_cat] = attid
                scores[expected_cat] = score
            elif cv2 is not None and crop.size:
                g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                if not self._is_empty_slot(g):
                    _save_unmatched(crop, posname, score)
        return result

    # ---------- nhận diện đầy đủ ----------
    def detect_weapons(self, img=None, threshold=None):
        """Chỉ OCR tên súng — dùng để quyết định balo có đang mở không."""
        if threshold is None:
            threshold = WEAPON_MATCH_THRESHOLD
        if img is None:
            img = self.capture()
        out = {}

        def _read_slot(key, slot):
            x, y, w, h = self.regions[key]
            crop = img[y:y + h, x:x + w]
            text = self._ocr(crop)
            wid, score = self.match(text, threshold=threshold)
            return slot, {
                "text": text,
                "weapon_id": wid,
                "score": round(score, 2),
                "attachments": None,
            }

        slots = (("slot1_name", 0), ("slot2_name", 1))
        with ThreadPoolExecutor(max_workers=2) as pool:
            for slot, data in pool.map(
                    lambda ks: _read_slot(*ks), slots):
                out[slot] = data
        out["inventory_open"] = any(out[s]["weapon_id"] for s in (0, 1))
        return out

    def detect(self, img=None, threshold=None, attachments=True):
        """Chụp ngay; OCR súng trước, phụ kiện chỉ khi có tên súng."""
        if threshold is None:
            threshold = WEAPON_MATCH_THRESHOLD
        if img is None:
            img = self.capture()
        out = self.detect_weapons(img, threshold)
        if not out.get("inventory_open"):
            return out
        if not attachments:
            return out
        for slot in (0, 1):
            entry = out[slot]
            if not entry.get("weapon_id"):
                continue
            w_obj = weapons.WEAPON_BY_ID.get(entry["weapon_id"])
            entry["attachments"] = self.detect_attachments(img, slot, w_obj)
        return out

    # ---------- vẽ overlay các ô phụ kiện + kết quả phân tích ----------
    # nhãn + màu (BGR) cho 5 ô theo thứ tự trong ATTACH_SLOTS
    BOX_LABELS = list(BOX_CATEGORIES)
    CAT_COLORS = {
        "scope": (255, 200, 0),    # lơ
        "muzzle": (0, 200, 255),   # cam
        "grip": (0, 255, 120),     # lục
        "mag": (255, 120, 220),    # hồng
        "stock": (200, 160, 255),  # tím nhạt
    }

    def annotate_boxes(self, img=None):
        """Vẽ TẤT CẢ ô mà bộ nhận diện chụp & phân tích lên ảnh, kèm kết quả
        + điểm khớp của từng ô, để kiểm tra vị trí ô đã chuẩn chưa.
        Trả ảnh đã vẽ (BGR)."""
        if cv2 is None:
            return None
        if img is None:
            img = self.capture()
        vis = img.copy()
        font = cv2.FONT_HERSHEY_SIMPLEX

        def _text(x, y, s, color, scale=0.5):
            cv2.putText(vis, s, (x, y), font, scale, (0, 0, 0), 3, cv2.LINE_AA)
            cv2.putText(vis, s, (x, y), font, scale, color, 1, cv2.LINE_AA)

        # --- vùng tên súng + OCR + súng nhận ra ---
        weps = {}
        for key, slot in (("slot1_name", 0), ("slot2_name", 1)):
            x, y, w, h = self.regions[key]
            crop = img[y:y + h, x:x + w]
            text = self._ocr(crop)
            wid, score = self.match(text)
            weps[slot] = weapons.WEAPON_BY_ID.get(wid) if wid else None
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 255), 2)
            _text(x, y - 6, f"{wid or '?'} '{text}' {score:.2f}", (0, 255, 255))

        # --- các ô phụ kiện của 2 súng (chỉ khi đã nhận ra tên súng) ---
        for slot in (0, 1):
            w_obj = weps.get(slot)
            if w_obj is None:
                continue
            for idx, box in enumerate(self.attach_slots.get(slot, [])):
                x, y, w, h = box
                expected_cat = BOX_CATEGORIES[idx] if idx < len(BOX_CATEGORIES) else f"#{idx}"
                cat = expected_cat
                color = self.CAT_COLORS.get(cat, (255, 255, 255))
                if not weapons.slot_enabled(w_obj, expected_cat):
                    cv2.rectangle(vis, (x, y), (x + w, y + h), (80, 80, 80), 1)
                    _text(x, y - 6, f"{cat}:N/A", (100, 100, 100), 0.45)
                    continue
                if expected_cat == "scope":
                    scope_ranked = self._match_scope_scores(img, box, None)
                    attid, sc = scope_ranked[0] if scope_ranked else (None, 0.0)
                    second = scope_ranked[1][1] if len(scope_ranked) > 1 else 0.0
                    sr = [("scope", attid, sc), ("scope", None, second)]
                    passed = bool(attid) and self._passes_threshold("scope", sc, sr)
                    rx0, ry0, rx1, ry1 = self.scope_matcher.scan_region(img, box)
                    cv2.rectangle(vis, (rx0, ry0), (rx1, ry1), (120, 120, 120), 1)
                else:
                    crop = img[y:y + h, x:x + w]
                    by_family = expected_cat == "muzzle"
                    ranked = self._match_icon_ranked(
                        crop, allowed=None, expected_cat=expected_cat,
                        group_muzzle_families=by_family)
                    if ranked:
                        cat, attid, sc = ranked[0]
                        if attid and by_family:
                            attid = normalize_muzzle_attid(attid, w_obj)
                        passed = self._passes_threshold(cat, sc, ranked)
                    else:
                        attid, sc, passed = None, 0.0, False
                draw_col = color if passed else (150, 150, 150)
                cv2.rectangle(vis, (x, y), (x + w, y + h), draw_col, 2)
                tag = f"{cat}:{attid or '-'} {sc:.2f}" + ("" if passed else "?")
                _text(x, y - 6, tag, draw_col, 0.45)
        return vis

    # ---------- xuất ảnh để hiệu chỉnh ----------
    def debug_dump(self, out_dir, img=None):
        if img is None:
            img = self.capture()
        os.makedirs(out_dir, exist_ok=True)
        vis = img.copy()
        for key, (x, y, w, h) in self.regions.items():
            cv2.rectangle(vis, (x, y), (x + w, y + h), (0, 255, 255), 2)
            crop = img[y:y + h, x:x + w]
            if crop.size:
                cv2.imwrite(os.path.join(out_dir, f"crop_{key}.png"), crop)
        cv2.imwrite(os.path.join(out_dir, "full_boxes.png"), vis)
        return out_dir
