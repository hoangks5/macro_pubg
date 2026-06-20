# -*- coding: utf-8 -*-
"""
Nhận diện phụ kiện HÀNG DƯỚI: muzzle / grip / stock / mag.

Mỗi ô inventory chỉ so khớp đúng 1 category (không lẫn grip vào ô muzzle).
Điểm khớp dùng tổng có trọng số (ưu tiên biên + silhouette) để chịu nền đổi màu.
"""

try:
    import cv2
except Exception:
    cv2 = None

from . import match_utils as mu

# Trọng số kênh khớp — raw dễ nhiễu nền nên thấp nhất.
SCORE_WEIGHTS = {"edge": 0.45, "silhouette": 0.35, "raw": 0.20}

# idx trong attach_slots -> category cố định của ô đó
BOX_CATEGORIES = ("scope", "muzzle", "grip", "stock")
LOWER_CATEGORIES = ("muzzle", "grip", "stock", "mag")

DEFAULT_THRESHOLDS = {
    "muzzle": 0.52,
    "grip": 0.58,
    "stock": 0.58,
    "mag": 0.58,
}

# Họ phụ kiện họng — nhận diện theo LOẠI (comp/flash/supp/brake) trước,
# không lọc theo súng; map sang attid đúng sau (vision.normalize_muzzle_attid).
MUZZLE_FAMILIES = {
    "comp": ("comp_ar", "comp_smg", "comp_sr"),
    "flash": ("flash_ar", "flash_smg", "flash_sr"),
    "supp": ("supp_ar", "supp_smg", "supp_sr"),
    "brake": ("muzzle_brake_ar",),
}
MUZZLE_ATTID_TO_FAMILY = {
    attid: fam
    for fam, ids in MUZZLE_FAMILIES.items()
    for attid in ids
}
# attid đại diện khi trả kết quả theo họ (trước khi map theo loại súng)
MUZZLE_FAMILY_CANONICAL = {
    "comp": "comp_ar",
    "flash": "flash_ar",
    "supp": "supp_ar",
    "brake": "muzzle_brake_ar",
}

# Icon PUBG giống nhau giữa nhóm AR / DMR — gom thêm mẫu cùng họ khi chấm điểm.
MUZZLE_TEMPLATE_ALIASES = {
    "supp_sr": ["supp_ar", "supp_smg"],
    "supp_ar": ["supp_sr", "supp_smg"],
    "supp_smg": ["supp_ar", "supp_sr"],
    "comp_sr": ["comp_ar", "comp_smg"],
    "comp_ar": ["comp_sr", "comp_smg"],
    "comp_smg": ["comp_ar", "comp_sr"],
    "flash_sr": ["flash_ar", "flash_smg"],
    "flash_ar": ["flash_sr", "flash_smg"],
    "flash_smg": ["flash_ar", "flash_sr"],
}


class AttachMatcher:
    def __init__(self, templates, thresholds=None):
        self.templates = templates
        self.thresholds = dict(DEFAULT_THRESHOLDS)
        if thresholds:
            self.set_thresholds(thresholds)

    def set_thresholds(self, thresholds):
        if not thresholds:
            return self.thresholds
        for cat, val in thresholds.items():
            if cat in self.thresholds:
                try:
                    self.thresholds[cat] = max(0.0, min(1.0, float(val)))
                except (TypeError, ValueError):
                    pass
        return self.thresholds

    @staticmethod
    def category_for_box_index(idx):
        """Category cố định của ô theo vị trí (bỏ qua scope ở idx=0)."""
        if 0 <= idx < len(BOX_CATEGORIES):
            return BOX_CATEGORIES[idx]
        return None

    def _score_direct(self, crop_gray, tmpl_gray):
        """Khớp trực tiếp crop game UI (giữ nền) — ổn định hơn khi mẫu cũng từ game."""
        best = -1.0
        for size in (48, 50, 52):
            a = mu.flatten_background(cv2.resize(crop_gray, (size, size)))
            b = mu.flatten_background(cv2.resize(tmpl_gray, (size, size)))
            raw = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED)[0, 0])
            edg = float(cv2.matchTemplate(
                mu.edge(a), mu.edge(b), cv2.TM_CCOEFF_NORMED)[0, 0])
            s = 0.35 * raw + 0.65 * edg
            if s > best:
                best = s
        return round(best, 3)

    def _score_template(self, core, tmpl, crop_gray=None):
        """Khớp lõi icon với 1 template ở vài tỉ lệ -> lấy điểm cao nhất."""
        core_e = mu.edge(core)
        core_s = mu.silhouette(core)
        best = -1.0
        for size in (52, 58, 64):
            t = mu.prep_icon(tmpl, size=size)
            t = cv2.resize(t, (core.shape[1], core.shape[0]))
            raw = float(cv2.matchTemplate(core, t, cv2.TM_CCOEFF_NORMED).max())
            edg = float(cv2.matchTemplate(core_e, mu.edge(t), cv2.TM_CCOEFF_NORMED).max())
            sil = float(cv2.matchTemplate(core_s, mu.silhouette(t), cv2.TM_CCOEFF_NORMED).max())
            s = (
                SCORE_WEIGHTS["raw"] * raw
                + SCORE_WEIGHTS["edge"] * edg
                + SCORE_WEIGHTS["silhouette"] * sil
            )
            if s > best:
                best = s
        if crop_gray is not None:
            th, tw = tmpl.shape[:2]
            direct = self._score_direct(crop_gray, tmpl)
            # crop inventory game (~50x50) — ưu tiên khớp trực tiếp giữ nền
            if th >= 40 and tw >= 40:
                best = max(best, direct)
            else:
                best = max(best, direct * 0.85)
        return round(best, 3)

    def _templates_for_attid(self, category, attid):
        """Lấy danh sách template của attid + alias (AR/DMR icon giống nhau)."""
        cat_tmpls = self.templates.get(category, {})
        out = list(cat_tmpls.get(attid, []))
        if category != "muzzle":
            return out
        for alias in MUZZLE_TEMPLATE_ALIASES.get(attid, []):
            out.extend(cat_tmpls.get(alias, []))
        return out

    def _templates_for_muzzle_family(self, family):
        """Gom mọi template thuộc cùng họ họng (comp/flash/supp/brake)."""
        cat_tmpls = self.templates.get("muzzle", {})
        seen = set()
        out = []
        for attid in MUZZLE_FAMILIES.get(family, ()):
            for tmpl in self._templates_for_attid("muzzle", attid):
                key = tmpl.tobytes()
                if key not in seen:
                    seen.add(key)
                    out.append(tmpl)
        return out

    def _match_muzzle_by_family(self, core, g):
        """Chấm điểm theo HỌ phụ kiện — không lọc theo loại súng."""
        ranked = []
        for fam in MUZZLE_FAMILIES:
            tmpls = self._templates_for_muzzle_family(fam)
            if not tmpls:
                continue
            best_s = 0.0
            for tmpl in tmpls:
                best_s = max(best_s, self._score_template(core, tmpl, g))
            if best_s > 0:
                ranked.append((MUZZLE_FAMILY_CANONICAL[fam], best_s))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def match_ranked(self, crop, category, allowed_ids=None, group_muzzle_families=False):
        """Trả [(attid, score), ...] giảm dần — CHỈ trong 1 category."""
        if cv2 is None or crop is None or crop.size == 0 or not category:
            return []
        g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        if mu.is_empty_slot(g):
            return []
        core = mu.prep_icon(g)
        if category == "muzzle" and group_muzzle_families:
            return self._match_muzzle_by_family(core, g)
        ranked = []
        candidates = self.templates.get(category, {})
        if allowed_ids is not None:
            attids = sorted(a for a in allowed_ids if a != "none")
        else:
            attids = sorted(a for a in candidates if a != "none")
        for attid in attids:
            tmpls = self._templates_for_attid(category, attid)
            if not tmpls:
                continue
            best_s = 0.0
            for tmpl in tmpls:
                best_s = max(best_s, self._score_template(core, tmpl, g))
            if best_s > 0:
                ranked.append((attid, best_s))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def match(self, crop, category, allowed_ids=None, apply_threshold=True,
              group_muzzle_families=False):
        """
        Trả (category, attid, score).
        category luôn là category của ô (không đoán chéo loại khác).
        """
        ranked = self.match_ranked(
            crop, category, allowed_ids, group_muzzle_families=group_muzzle_families)
        if not ranked:
            return category, None, 0.0
        attid, score = ranked[0]
        scores_only = [s for _, s in ranked]
        thr = self.thresholds.get(category, 0.58)
        if apply_threshold and not mu.passes_threshold(thr, score, scores_only):
            return category, None, round(score, 3)
        return category, attid, round(score, 3)

    def detect_slot_attachments(self, img, boxes, allowed=None, on_unmatched=None):
        """
        Nhận diện muzzle/grip/stock từ danh sách ô (bỏ idx=0 scope).
        allowed: dict {cat: set(attid)} — lọc template hợp lệ theo súng.
        on_unmatched(crop, category, score) — callback khi ô có icon nhưng chưa khớp.
        Trả dict {cat: attid} và dict điểm {cat: score}.
        """
        result = {}
        scores = {}
        for idx, box in enumerate(boxes):
            cat = self.category_for_box_index(idx)
            if cat is None or cat == "scope":
                continue
            x, y, w, h = box
            crop = img[y:y + h, x:x + w]
            allow_set = None if allowed is None else allowed.get(cat)
            matched_cat, attid, score = self.match(crop, cat, allow_set)
            if attid:
                result[cat] = attid
                scores[cat] = score
            elif on_unmatched and cv2 is not None and crop.size:
                g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                if not mu.is_empty_slot(g):
                    on_unmatched(crop, cat, score)
        return result, scores
