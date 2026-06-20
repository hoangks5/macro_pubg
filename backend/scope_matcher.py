# -*- coding: utf-8 -*-
"""
Nhận diện SCOPE (ô trên thân súng).

Scope nằm trên thân súng 3D -> bị che bởi skin/model, nền đổi theo từng súng.
Chiến lược:
  1) Khớp trực tiếp crop game UI (50x50) — ưu tiên biên, nhiều tỉ lệ cắt trên.
  2) Dò trượt trong vùng pad (scope lệch vị trí theo súng).
  3) Khớp phần TRÊN của ô (bỏ thân súng che dưới) ở vài tỉ lệ — lấy điểm cao nhất.
"""

try:
    import cv2
except Exception:
    cv2 = None

from . import match_utils as mu

SCOPE_SCAN_PAD_Y = 28
SCOPE_SCAN_PAD_X = 12
# Thử vài tỉ lệ cắt phía trên — 0.85 quá thấp, còn nhiều thân súng gây nhiễu.
SCOPE_TOP_RATIOS = (0.65, 0.70, 0.85)
SCOPE_SCORE_WEIGHTS = {"edge": 0.65, "silhouette": 0.25, "raw": 0.10}

DEFAULT_SCOPE_THRESHOLD = 0.52
SCOPE_MATCH_MARGIN = 0.05
SCOPE_MATCH_FLOOR = 0.38


class ScopeMatcher:
    def __init__(self, templates, threshold=None):
        self.templates = templates
        self.threshold = float(threshold if threshold is not None else DEFAULT_SCOPE_THRESHOLD)

    def set_threshold(self, value):
        try:
            self.threshold = max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            pass
        return self.threshold

    @staticmethod
    def _scope_top(gray, ratio):
        """Cắt phần trên ô scope — giảm nhiễu thân súng/skin che phía dưới."""
        if gray is None or gray.size == 0:
            return gray
        h = gray.shape[0]
        cut = max(8, int(h * ratio))
        return gray[:cut, :]

    @staticmethod
    def _is_fullframe_template(tmpl):
        if tmpl is None:
            return False
        h, w = tmpl.shape[:2]
        return h >= 40 and w >= 40

    def _score_channels(self, a, b):
        """Điểm có trọng số — ưu tiên biên, ít phụ thuộc màu nền skin."""
        raw = float(cv2.matchTemplate(a, b, cv2.TM_CCOEFF_NORMED).max())
        ae, be = mu.edge(a), mu.edge(b)
        edg = float(cv2.matchTemplate(ae, be, cv2.TM_CCOEFF_NORMED).max())
        sil = float(cv2.matchTemplate(
            mu.silhouette(a), mu.silhouette(b), cv2.TM_CCOEFF_NORMED).max())
        return (
            SCOPE_SCORE_WEIGHTS["raw"] * raw
            + SCOPE_SCORE_WEIGHTS["edge"] * edg
            + SCOPE_SCORE_WEIGHTS["silhouette"] * sil
        )

    def _score_direct_pair(self, crop_gray, tmpl_gray):
        """Khớp trực tiếp một cặp ảnh — đa kích thước + nhiều tỉ lệ cắt trên."""
        best = -1.0
        for size in (48, 50, 52):
            a = mu.flatten_background(cv2.resize(crop_gray, (size, size)))
            b = mu.flatten_background(cv2.resize(tmpl_gray, (size, size)))
            best = max(best, self._score_channels(a, b))
            for ratio in SCOPE_TOP_RATIOS:
                at = self._scope_top(a, ratio)
                bt = self._scope_top(b, ratio)
                if at.size and bt.size and at.shape[0] >= 6 and bt.shape[0] >= 6:
                    bt_r = cv2.resize(bt, (at.shape[1], at.shape[0]))
                    best = max(best, self._score_channels(at, bt_r))
        return round(best, 3)

    def _score_direct_box(self, crop_gray, tmpl_gray):
        return self._score_direct_pair(crop_gray, tmpl_gray)

    def _score_icon_core(self, crop_gray, tmpl_gray):
        """Khớp lõi icon — bổ sung khi template là icon cắt sát (không full frame)."""
        th, tw = tmpl_gray.shape[:2]
        if th >= 40 and tw >= 40:
            return 0.0
        core = mu.prep_icon(crop_gray)
        best = -1.0
        for size in (52, 58, 64):
            t = mu.prep_icon(tmpl_gray, size=size)
            t = cv2.resize(t, (core.shape[1], core.shape[0]))
            raw = float(cv2.matchTemplate(core, t, cv2.TM_CCOEFF_NORMED).max())
            edg = float(cv2.matchTemplate(
                mu.edge(core), mu.edge(t), cv2.TM_CCOEFF_NORMED).max())
            sil = float(cv2.matchTemplate(
                mu.silhouette(core), mu.silhouette(t), cv2.TM_CCOEFF_NORMED).max())
            s = (
                SCOPE_SCORE_WEIGHTS["raw"] * raw
                + SCOPE_SCORE_WEIGHTS["edge"] * edg
                + SCOPE_SCORE_WEIGHTS["silhouette"] * sil
            )
            best = max(best, s)
        return round(best, 3)

    def _score_sliding(self, region_gray, tmpl_gray, tw, th):
        """Dò trượt trong vùng pad — scope xê dọc/ngang theo từng súng."""
        g = mu.flatten_background(region_gray)
        rh, rw = g.shape[:2]
        if tw < 8 or th < 8 or tw > rw or th > rh:
            return 0.0
        best = -1.0
        t = mu.flatten_background(cv2.resize(tmpl_gray, (tw, th)))
        raw = float(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED).max())
        edg = float(cv2.matchTemplate(
            mu.edge(g), mu.edge(t), cv2.TM_CCOEFF_NORMED).max())
        sil = float(cv2.matchTemplate(
            mu.silhouette(g), mu.silhouette(t), cv2.TM_CCOEFF_NORMED).max())
        best = max(
            best,
            SCOPE_SCORE_WEIGHTS["raw"] * raw
            + SCOPE_SCORE_WEIGHTS["edge"] * edg
            + SCOPE_SCORE_WEIGHTS["silhouette"] * sil,
        )
        for ratio in SCOPE_TOP_RATIOS:
            gt = self._scope_top(g, ratio)
            tt = self._scope_top(t, ratio)
            if gt.size and tt.size and gt.shape[0] >= 6 and tt.shape[0] >= 6:
                tt_r = cv2.resize(tt, (gt.shape[1], gt.shape[0]))
                best = max(best, self._score_channels(gt, tt_r))
        return round(best, 3)

    def _score_template(self, crop_gray, region_gray, tmpl_gray, box_w, box_h):
        """Chọn phương pháp khớp theo loại template."""
        s = 0.0
        if self._is_fullframe_template(tmpl_gray):
            s = max(s, self._score_direct_box(crop_gray, tmpl_gray))
        s = max(s, self._score_icon_core(crop_gray, tmpl_gray))
        for tw, th in ((box_w - 6, box_h - 6), (box_w, box_h), (box_w + 6, box_h + 6)):
            s = max(s, self._score_sliding(region_gray, tmpl_gray, tw, th))
        return round(s, 3)

    def match_ranked(self, img, box, allowed_ids=None):
        """Trả [(attid, score), ...] giảm dần."""
        if cv2 is None or img is None:
            return []
        x, y, w, h = box
        H, W = img.shape[:2]
        y0 = max(0, y - SCOPE_SCAN_PAD_Y)
        y1 = min(H, y + h + SCOPE_SCAN_PAD_Y)
        x0 = max(0, x - SCOPE_SCAN_PAD_X)
        x1 = min(W, x + w + SCOPE_SCAN_PAD_X)
        region = img[y0:y1, x0:x1]
        if region is None or region.size == 0:
            return []
        crop = img[y:y + h, x:x + w]
        crop_g = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        region_g = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

        per_attid = {}
        for attid, tmpls in self.templates.get("scope", {}).items():
            if attid == "none":
                continue
            if allowed_ids is not None and attid not in allowed_ids:
                continue
            best_s = 0.0
            for tmpl in tmpls:
                best_s = max(best_s, self._score_template(crop_g, region_g, tmpl, w, h))
            if best_s > 0:
                per_attid[attid] = round(best_s, 3)
        return sorted(per_attid.items(), key=lambda x: x[1], reverse=True)

    def _passes_threshold(self, score, ranked_scores):
        if score >= self.threshold:
            return True
        second = ranked_scores[1] if len(ranked_scores) > 1 else 0.0
        return score >= SCOPE_MATCH_FLOOR and (score - second) >= SCOPE_MATCH_MARGIN

    def match(self, img, box, allowed_ids=None, apply_threshold=True):
        ranked = self.match_ranked(img, box, allowed_ids)
        if not ranked:
            return None, 0.0
        attid, score = ranked[0]
        if apply_threshold:
            scores = [s for _, s in ranked]
            if not self._passes_threshold(score, scores):
                return None, round(score, 3)
        return attid, round(score, 3)

    def scan_region(self, img, box):
        x, y, w, h = box
        H, W = img.shape[:2]
        return (
            max(0, x - SCOPE_SCAN_PAD_X),
            max(0, y - SCOPE_SCAN_PAD_Y),
            min(W, x + w + SCOPE_SCAN_PAD_X),
            min(H, y + h + SCOPE_SCAN_PAD_Y),
        )
