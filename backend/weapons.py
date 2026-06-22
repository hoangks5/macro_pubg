# -*- coding: utf-8 -*-
"""
Cơ sở dữ liệu súng và phụ kiện của PUBG (dùng cho macro giảm giật).

Các con số "recoil" là PIXEL kéo xuống cho MỖI VIÊN đạn ở sensitivity = 1.0.
Đây là giá trị khởi điểm mang tính tương đối giữa các súng — bạn tinh chỉnh
lại bằng thanh "Độ nhạy" (sensitivity) trong giao diện cho khớp với in-game
sensitivity / DPI chuột của mình.

rpm      = tốc độ bắn (viên/phút) -> dùng để tính số viên mỗi giây.
recoil   = pixel kéo XUỐNG / viên (chỉ giật dọc).
"""

# ---------------------------------------------------------------------------
# DANH SÁCH SÚNG  (chỉ giật dọc)
# ---------------------------------------------------------------------------
WEAPONS = [
    # --- Assault Rifles ---
    {"id": "m416",    "name": "M416",        "type": "AR",  "rpm": 700, "recoil": 22.1},
    {"id": "akm",     "name": "AKM",         "type": "AR",  "rpm": 600, "recoil": 31.7},
    {"id": "scarl",   "name": "SCAR-L",      "type": "AR",  "rpm": 650, "recoil": 23.4},
    {"id": "m16a4",   "name": "M16A4",       "type": "AR",  "rpm": 900, "recoil": 19.3},
    {"id": "m762",    "name": "Beryl M762",  "type": "AR",  "rpm": 700, "recoil": 40.0},
    {"id": "g36c",    "name": "G36C",        "type": "AR",  "rpm": 650, "recoil": 22.8},
    {"id": "aug",     "name": "AUG A3",      "type": "AR",  "rpm": 700, "recoil": 18.6},
    {"id": "qbz",     "name": "QBZ95",       "type": "AR",  "rpm": 650, "recoil": 22.1},
    {"id": "mk47",    "name": "Mk47 Mutant", "type": "AR",  "rpm": 600, "recoil": 30.3},
    {"id": "groza",   "name": "Groza",       "type": "AR",  "rpm": 700, "recoil": 29.0},
    {"id": "k2",      "name": "K2",          "type": "AR",  "rpm": 670, "recoil": 23.4},
    {"id": "ace32",   "name": "ACE32",       "type": "AR",  "rpm": 600, "recoil": 26.9},
    {"id": "famas",   "name": "FAMAS",       "type": "AR",  "rpm": 1100,"recoil": 20.0},

    # --- SMG ---
    {"id": "ump45",   "name": "UMP45",       "type": "SMG", "rpm": 600, "recoil": 15.2},
    {"id": "vector",  "name": "Vector",      "type": "SMG", "rpm": 1100,"recoil": 9.7},
    {"id": "tommy",   "name": "Tommy Gun",   "type": "SMG", "rpm": 700, "recoil": 15.9},
    {"id": "mp5k",    "name": "MP5K",        "type": "SMG", "rpm": 900, "recoil": 11.7},
    {"id": "pp19",    "name": "PP-19 Bizon", "type": "SMG", "rpm": 700, "recoil": 12.4},
    {"id": "p90",     "name": "P90",         "type": "SMG", "rpm": 950, "recoil": 11.0},
    {"id": "uzi",     "name": "Micro UZI",   "type": "SMG", "rpm": 1200,"recoil": 9.7},
    {"id": "js9",     "name": "JS9",         "type": "SMG", "rpm": 750, "recoil": 11.7},

    # --- LMG ---
    {"id": "m249",    "name": "M249",        "type": "LMG", "rpm": 750, "recoil": 24.8},
    {"id": "dp28",    "name": "DP-28",       "type": "LMG", "rpm": 550, "recoil": 26.9},
    {"id": "mg3",     "name": "MG3",         "type": "LMG", "rpm": 990, "recoil": 29.0},

    # --- DMR (auto / bán tự động) ---
    {"id": "mini14",  "name": "Mini 14",     "type": "DMR", "rpm": 350, "recoil": 18.6},
    {"id": "sks",     "name": "SKS",         "type": "DMR", "rpm": 350, "recoil": 31.7},
    {"id": "slr",     "name": "SLR",         "type": "DMR", "rpm": 320, "recoil": 38.6},
    {"id": "qbu",     "name": "QBU",         "type": "DMR", "rpm": 350, "recoil": 22.1},
    {"id": "mk12",    "name": "Mk12",        "type": "DMR", "rpm": 400, "recoil": 23.4},
    {"id": "mk14",    "name": "Mk14 (Auto)", "type": "DMR", "rpm": 700, "recoil": 42.8},
    {"id": "vss",     "name": "VSS",         "type": "DMR", "rpm": 600, "recoil": 14.5},
    {"id": "dragunov","name": "Dragunov",    "type": "DMR", "rpm": 400, "recoil": 33.1},
    {"id": "m24",     "name": "M24",         "type": "SR",  "rpm": 60,  "recoil": 35.0},
    {"id": "awm",     "name": "AWM",         "type": "SR",  "rpm": 60,  "recoil": 45.0},
    {"id": "win94",   "name": "Win94",       "type": "SR",  "rpm": 56,  "recoil": 28.0},
    {"id": "lynx_amr","name": "Lynx AMR",    "type": "SR",  "rpm": 45,  "recoil": 52.0},

    # --- Pistol (full-auto) ---
    {"id": "p18c",    "name": "P18C",        "type": "PISTOL", "rpm": 850, "recoil": 11.0},
    {"id": "skorpion","name": "Skorpion",    "type": "PISTOL", "rpm": 850, "recoil": 11.7},
]

# ---------------------------------------------------------------------------
# GIAI ĐOẠN BĂNG ĐẠN
#   Giật PUBG tăng dần theo số viên: vài viên đầu nhẹ -> giữa băng mạnh ->
#   cuối / băng mở rộng mạnh nhất. Chia làm 4 mốc:
#       viên 1-10  |  11-20  |  21-30  |  30+ (băng mở rộng)
# ---------------------------------------------------------------------------
PHASE_LABELS = ["1-10", "11-20", "21-30", "30+"]
PHASE_BOUNDS = [10, 20, 30]               # ngưỡng số viên để đổi giai đoạn
PHASE_FACTORS = [0.85, 1.00, 1.10, 1.15]  # hệ số mặc định so với 'recoil' gốc

# Sinh sẵn 4 giá trị giật cho mỗi súng (có thể chỉnh từng giá trị trong UI)
for _w in WEAPONS:
    _base = _w["recoil"]
    _w["recoil_phases"] = [round(_base * f, 1) for f in PHASE_FACTORS]

# ---------------------------------------------------------------------------
# PHỤ KIỆN
#   vert = hệ số nhân độ giật DỌC (càng nhỏ càng giảm)
#   fits = danh sách LOẠI súng dùng được phụ kiện này ("ALL" = mọi loại).
#          Dùng để lọc danh sách theo súng + để biết icon thuộc nhóm AR/SMG/SR.
#
# Họng súng (muzzle) trong PUBG có biến thể RIÊNG cho từng nhóm nòng
# (AR / SMG / Sniper) — icon khác nhau nên phải tách để nhận diện đúng.
# ---------------------------------------------------------------------------
ATTACHMENTS = {
    # Ống ngắm KHÔNG giảm giật — nhưng độ phóng đại làm giật DỌC trên màn hình
    # bị KHUẾCH ĐẠI theo bội số zoom. Red Dot/Holo = 1x (vert 1.0); 2x trở lên
    # cần kéo nhiều hơn -> vert > 1 (xấp xỉ bằng bội số phóng đại).
    "scope": [
        {"id": "none",    "name": "— Không —",  "vert": 1.00, "fits": "ALL", "desc": ""},
        {"id": "red_dot", "name": "Red Dot",    "vert": 1.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Ngắm điểm đỏ (1x)"},
        {"id": "holo",    "name": "Holographic", "vert": 1.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Ngắm holo (1x)"},
        {"id": "hybrid",  "name": "Hybrid Sight","vert": 1.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Ngắm lai / canted (1x)"},
        {"id": "2x",      "name": "2x Scope",   "vert": 2.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Phóng đại 2x"},
        {"id": "3x",      "name": "3x Scope",   "vert": 3.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Phóng đại 3x"},
        {"id": "4x",      "name": "4x Scope",   "vert": 4.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Phóng đại 4x"},
        {"id": "6x",      "name": "6x Scope",   "vert": 6.00, "fits": ["AR", "SMG", "DMR", "LMG"], "desc": "Phóng đại 6x (điều chỉnh được)"},
        {"id": "8x",      "name": "8x Scope",   "vert": 8.00, "fits": ["DMR"], "desc": "Phóng đại 8x"},
        {"id": "15x",     "name": "15x Scope",  "vert": 8.00, "fits": ["DMR"], "desc": "Phóng đại 15x (điều chỉnh được)"},
    ],
    # Họng súng PUBG chỉ có 3 dòng: Compensator / Flash Hider / Suppressor,
    # mỗi dòng có biến thể RIÊNG cho nhóm AR / SMG / Sniper(DMR) -> icon khác nhau.
    "muzzle": [
        {"id": "none",      "name": "— Không —",            "vert": 1.00, "fits": "ALL",   "desc": ""},
        # --- nhóm AR (icon dùng chung cho AR, một số DMR, S12K) ---
        {"id": "comp_ar",        "name": "Compensator (AR)",  "vert": 0.75, "fits": ["AR"],         "desc": "Giảm giật dọc mạnh nhất (AR)"},
        {"id": "muzzle_brake_ar","name": "Muzzle Brake (AR)", "vert": 0.82, "fits": ["AR", "DMR"],  "desc": "Giảm giật ngang + dọc (AR/DMR)"},
        {"id": "flash_ar",       "name": "Flash Hider (AR)",  "vert": 0.88, "fits": ["AR"],         "desc": "Giảm giật dọc khá (AR)"},
        {"id": "supp_ar",        "name": "Suppressor (AR)",   "vert": 0.93, "fits": ["AR"],         "desc": "Giảm nhẹ, giấu tiếng (AR)"},
        # --- nhóm SMG ---
        {"id": "comp_smg",  "name": "Compensator (SMG)",    "vert": 0.75, "fits": ["SMG"], "desc": "Giảm giật dọc mạnh nhất (SMG)"},
        {"id": "flash_smg", "name": "Flash Hider (SMG)",    "vert": 0.88, "fits": ["SMG"], "desc": "Giảm giật dọc khá (SMG)"},
        {"id": "supp_smg",  "name": "Suppressor (SMG)",     "vert": 0.93, "fits": ["SMG"], "desc": "Giảm nhẹ, giấu tiếng (SMG)"},
        # --- nhóm Sniper / DMR ---
        {"id": "comp_sr",   "name": "Compensator (Sniper)", "vert": 0.78, "fits": ["DMR"], "desc": "Giảm giật cho DMR/SR"},
        {"id": "flash_sr",  "name": "Flash Hider (Sniper)", "vert": 0.90, "fits": ["DMR"], "desc": "Giảm giật khá cho DMR/SR"},
        {"id": "supp_sr",   "name": "Suppressor (Sniper)",  "vert": 0.93, "fits": ["DMR"], "desc": "Giảm nhẹ, giấu tiếng (SR)"},
    ],
    "grip": [
        {"id": "none",      "name": "— Không —",     "vert": 1.00, "fits": "ALL",                  "desc": ""},
        {"id": "vertical",  "name": "Vertical Grip", "vert": 0.82, "fits": ["AR", "SMG", "DMR"],   "desc": "Giảm giật dọc mạnh"},
        {"id": "half",      "name": "Half Grip",     "vert": 0.89, "fits": ["AR", "SMG"],          "desc": "Cân bằng + hồi nhanh"},
        {"id": "thumb",     "name": "Thumb Grip",    "vert": 0.86, "fits": ["AR", "SMG", "DMR"],   "desc": "Giảm giật dọc, ADS nhanh"},
        {"id": "angled",    "name": "Angled Grip",   "vert": 0.96, "fits": ["AR", "SMG", "DMR"],   "desc": "Hồi giật nhanh"},
        {"id": "light",     "name": "Light Grip",    "vert": 0.91, "fits": ["AR", "SMG", "DMR"],   "desc": "Giảm nhẹ, hồi nhanh"},
        {"id": "laser",     "name": "Laser Sight",   "vert": 0.99, "fits": ["AR", "SMG", "DMR", "PISTOL"], "desc": "Giảm văng khi bắn lia"},
    ],
    "stock": [
        {"id": "none",        "name": "— Không —",      "vert": 1.00, "fits": "ALL",          "desc": ""},
        {"id": "tactical",    "name": "Tactical Stock", "vert": 0.88, "fits": ["AR", "SMG"],  "desc": "Giảm giật, hồi nhanh"},
        {"id": "heavy",       "name": "Heavy Stock",    "vert": 0.84, "fits": ["AR"],        "desc": "Báng nặng (ACE32)"},
        {"id": "cheek",       "name": "Cheek Pad",      "vert": 0.92, "fits": ["DMR"],        "desc": "Giảm giật dọc khi ngắm"},
        {"id": "bullet_loops","name": "Bullet Loops",   "vert": 1.00, "fits": ["DMR"],        "desc": "Nạp đạn nhanh (DMR)"},
        {"id": "uzi_stock",   "name": "Stock (Micro UZI)","vert": 0.90, "fits": ["SMG"],      "desc": "Báng cho Micro UZI"},
    ],
    "mag": [
        {"id": "none",      "name": "— Không —",     "vert": 1.00, "fits": "ALL", "desc": ""},
        {"id": "extended",  "name": "Extended Mag",  "vert": 1.00, "fits": ["AR", "SMG", "DMR", "LMG", "PISTOL"], "desc": "Tăng số đạn"},
        {"id": "quickdraw", "name": "QuickDraw Mag", "vert": 1.00, "fits": ["AR", "SMG", "DMR", "LMG", "PISTOL"], "desc": "Nạp đạn nhanh"},
        {"id": "ext_quick", "name": "Ext. QuickDraw", "vert": 1.00,"fits": ["AR", "SMG", "DMR", "LMG", "PISTOL"], "desc": "Nhiều đạn + nạp nhanh"},
    ],
}

# Map nhanh để tra cứu
WEAPON_BY_ID = {w["id"]: w for w in WEAPONS}

# ---------------------------------------------------------------------------
# NGOẠI LỆ THEO TỪNG SÚNG — slot = False -> súng KHÔNG có ô phụ kiện đó
# (bỏ qua nhận diện + UI chỉ còn "— Không —").
# Nguồn: slot phụ kiện thực tế trong PUBG (pubg.wiki.gg).
# ---------------------------------------------------------------------------
WEAPON_SLOTS = {
    # --- AR ---
    "akm":   {"grip": False, "stock": False},
    "scarl": {"stock": False},                  # không Tactical Stock
    "m16a4": {"grip": False},                   # có stock, không lower rail
    "m762":  {"stock": False},
    "g36c":  {"stock": False},
    "aug":   {"stock": False},                  # bullpup
    "qbz":   {"stock": False},
    "groza": {"grip": False, "stock": False},
    "k2":    {"grip": False, "stock": False},
    "famas": {"grip": False, "stock": False},
    # --- SMG ---
    "ump45": {"stock": False},
    "tommy": {"stock": False},
    "pp19":  {"stock": False},
    "p90":   {"grip": False, "muzzle": False, "stock": False, "scope": False},
    "uzi":   {"grip": False},                   # chỉ stock riêng (uzi_stock)
    "js9":   {"grip": False, "stock": False},   # bullpup
    # --- LMG ---
    "m249":  {"muzzle": False, "grip": False},  # scope + mag + tactical stock
    "dp28":  {"muzzle": False, "grip": False, "stock": False, "mag": False},
    "mg3":   {"muzzle": False, "grip": False, "stock": False, "mag": False},
    # --- DMR ---
    "mini14": {"grip": False, "stock": False},
    "dragunov": {"grip": False},
    "vss":    {"muzzle": False, "grip": False, "scope": False},
    # --- SR (bolt) ---
    "m24":    {"grip": False, "mag": False},
    "awm":    {"grip": False, "mag": False},
    "win94":  {"muzzle": False, "grip": False, "stock": False, "mag": False},
    "lynx_amr":{"muzzle": False, "grip": False, "stock": False, "mag": False},
    # --- Pistol ---
    "p18c":   {"stock": False},
}

# Giới hạn attid theo súng (ngoài lọc fits theo loại AR/SMG/DMR).
WEAPON_ATTACH_IDS = {
    "ace32":    {"stock": ["tactical", "heavy"]},
    "uzi":      {"stock": ["uzi_stock"]},
    "skorpion": {"stock": ["uzi_stock"]},
}

# Các loại slot phụ kiện theo thứ tự hiển thị
ATTACH_CATEGORIES = ("scope", "muzzle", "grip", "stock", "mag")


def slot_enabled(weapon, category):
    """True nếu súng có ô phụ kiện category (được phép nhận diện / chọn)."""
    if weapon is None:
        return True
    return WEAPON_SLOTS.get(weapon["id"], {}).get(category) is not False


def apply_weapon_slots(overrides):
    """Gộp thêm cấu hình slot từ config.json (weapon_id -> {grip: false, ...})."""
    for wid, slots in (overrides or {}).items():
        if not isinstance(slots, dict):
            continue
        entry = WEAPON_SLOTS.setdefault(wid, {})
        for cat, val in slots.items():
            if cat in ATTACH_CATEGORIES and val is False:
                entry[cat] = False


def sanitize_attachments(weapon_id, attachments):
    """Đặt 'none' cho slot súng không có (AKM grip/stock, M762 stock...)."""
    w = WEAPON_BY_ID.get(weapon_id)
    if not w or not attachments:
        return attachments
    out = dict(attachments)
    for cat in ATTACH_CATEGORIES:
        if not slot_enabled(w, cat):
            out[cat] = "none"
    return out


def allowed_attachments(weapon, category, data=None):
    """
    Trả danh sách phụ kiện HỢP LỆ cho 1 súng ở 1 category.
    - "— Không —" luôn có mặt.
    - Lọc theo 'fits' (loại súng) + ngoại lệ trong WEAPON_SLOTS.
    weapon: dict súng (hoặc None -> trả tất cả).
    """
    data = data or ATTACHMENTS
    items = data.get(category, [])
    if weapon is None:
        return list(items)
    # slot bị khoá -> chỉ còn "none"
    if WEAPON_SLOTS.get(weapon["id"], {}).get(category) is False:
        return [a for a in items if a["id"] == "none"] or list(items[:1])
    wtype = weapon.get("type")
    # SR (bolt) dùng chung pool phụ kiện icon với DMR trong PUBG
    if wtype == "SR":
        wtype = "DMR"
    restrict = WEAPON_ATTACH_IDS.get(weapon["id"], {}).get(category)
    out = []
    for a in items:
        fits = a.get("fits")
        if a["id"] == "none" or fits == "ALL" or (isinstance(fits, (list, tuple)) and wtype in fits):
            if restrict is not None and a["id"] != "none" and a["id"] not in restrict:
                continue
            out.append(a)
    return out


def combined_multiplier(attachments_sel, attachments_data=None):
    """
    Trả về hệ số nhân giật DỌC từ tổ hợp phụ kiện.
    attachments_data: dict phụ kiện (mặc định hoặc đã được người dùng chỉnh).
    """
    attachments_sel = attachments_sel or {}
    data = attachments_data or ATTACHMENTS
    v = 1.0
    for cat in ATTACH_CATEGORIES:
        aid = attachments_sel.get(cat, "none")
        a = next((x for x in data.get(cat, []) if x["id"] == aid), None)
        if a:
            v *= a.get("vert", 1.0)
    return v


def compute_profile(weapon, attachments_sel, attachments_data=None, sensitivity=1.0):
    """
    Tính profile cho engine từ dict SÚNG (đã áp chỉnh sửa của người dùng nếu có).
    Trả về 4 giai đoạn băng đạn, mỗi giai đoạn có lực kéo riêng:
      phases[i] = {label, recoil_per_shot, pull_per_sec}
    """
    if not weapon:
        return None
    mult_v = combined_multiplier(attachments_sel, attachments_data)
    shots_per_sec = weapon["rpm"] / 60.0
    base_phases = weapon.get("recoil_phases") or [weapon.get("recoil", 0.0)] * 4

    phases = []
    for i, r in enumerate(base_phases):
        rps = r * mult_v * sensitivity
        phases.append({
            "label": PHASE_LABELS[i] if i < len(PHASE_LABELS) else "+",
            "recoil_per_shot": round(rps, 3),
            "pull_per_sec": rps * shots_per_sec,
        })

    return {
        "weapon_id": weapon["id"],
        "weapon_name": weapon["name"],
        "type": weapon["type"],
        "rpm": weapon["rpm"],
        "shots_per_sec": round(shots_per_sec, 2),
        "mult": round(mult_v, 3),
        "phases": phases,
        "phase_bounds": PHASE_BOUNDS,
    }
