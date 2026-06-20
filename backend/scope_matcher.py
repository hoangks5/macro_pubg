# -*- coding: utf-8 -*-
"""
Nhận diện SCOPE (ô trên thân súng).

Scope nằm trên thân súng 3D -> bị che bởi skin/model, nền đổi theo từng súng.
Chiến lược:
  1) Khớp trực tiếp crop game UI (50x50, giữ nền) — ưu tiên biến thể @sks/@aug.
  2) Dò trượt trong vùng pad (scope lệch vị trí theo súng).
  3) Khớp phần TRÊN của ô (bỏ ~15% dưới — thân súng hay che).
Không nên hạ ngưỡng quá thấp; dùng margin giữa #1 và #2 thay vì bỏ qua accuracy.
"""

try:
    import cv2
except Exception:
    cv2 = None

from . import match_utils as mu

SCOPE_SCAN_PAD_Y = 28
SCOPE_SCAN_PAD_X = 12
SCOPE_TOP_RATIO = 0.85          # chỉ lấy phần trên ô — bớt thân súng che dưới
SCOPE_SCORE_WEIGHTS = {"edge": 0.50, "silhouette": 0.30, "raw": 0.20}

DEFAULT_SCOPE_THRESHOLD = 0.52
SCOPE_MATCH_MARGIN = 0.06
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
    def _scope_top(gray, ratio=SCOPE_TOP_RATIO):
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
        """Điểm có trọng số — ưu tiên biên/silhouette, ít phụ thuộc màu nền skin."""
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

    def _score_direct_box(self, crop_gray, tmpl_gray):
        """Khớp crop inventory với template cùng kiểu (full frame 50x50)."""
        best = -1.0
        ch, cw = crop_gray.shape[:2]
        th, tw = tmpl_gray.shape[:2]
        for size in (48, 50, 52):
            a = mu.flatten_background(cv2.resize(crop_gray, (size, size)))
            b = mu.flatten_background(cv2.resize(tmpl_gray, (size, size)))
            best = max(best, self._score_channels(a, b))
            at = self._scope_top(a)
            bt = self._scope_top(b)
            if at.size and bt.size:
                bt_r = cv2.resize(bt, (at.shape[1], at.shape[0]))
                best = max(best, self._score_channels(at, bt_r))
        return round(best, 3)

    def _score_sliding(self, region_gray, tmpl_gray, tw, th):
        """Dò trượt trong vùng pad — scope xê dọc/ngang theo từng súng."""
        g = mu.flatten_background(region_gray)
        g_e = mu.edge(g)
        g_s = mu.silhouette(g)
        rh, rw = g.shape[:2]
        if tw < 8 or th < 8 or tw > rw or th > rh:
            return 0.0
        best = -1.0
        t = mu.flatten_background(cv2.resize(tmpl_gray, (tw, th)))
        t_e, t_s = mu.edge(t), mu.silhouette(t)
        raw = float(cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED).max())
        edg = float(cv2.matchTemplate(g_e, t_e, cv2.TM_CCOEFF_NORMED).max())
        sil = float(cv2.matchTemplate(g_s, t_s, cv2.TM_CCOEFF_NORMED).max())
        best = max(best, raw, edg, sil)
        gt = self._scope_top(g)
        tt = self._scope_top(t)
        if gt.size and tt.size:
            tt_r = cv2.resize(tt, (gt.shape[1], gt.shape[0]))
            best = max(best, float(cv2.matchTemplate(
                gt, tt_r, cv2.TM_CCOEFF_NORMED).max()))
        return round(best, 3)

    def _score_template(self, crop_gray, region_gray, tmpl_gray, box_w, box_h):
        """Chọn phương pháp khớp theo loại template."""
        if self._is_fullframe_template(tmpl_gray):
            s = self._score_direct_box(crop_gray, tmpl_gray)
        else:
            s = 0.0
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
        crop_g = mu.flatten_background(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY))
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
