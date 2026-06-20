# -*- coding: utf-8 -*-
"""Tiện ích xử lý ảnh dùng chung cho nhận diện phụ kiện."""

try:
    import numpy as np
except Exception:
    np = None

try:
    import cv2
except Exception:
    cv2 = None

MATCH_MARGIN = 0.10
MATCH_FLOOR = 0.38


def is_empty_slot(gray, min_std=11.0):
    """Ô chưa gắn phụ kiện gần như đồng màu -> độ lệch chuẩn thấp."""
    if gray is None or gray.size == 0:
        return True
    flat = flatten_background(gray)
    return float(flat.std()) < min_std


def flatten_background(gray):
    """Trừ nền ước lượng từ viền ô — giảm nhiễu khi nền item đổi màu theo súng/skin."""
    if gray is None or gray.size == 0 or np is None:
        return gray
    h, w = gray.shape[:2]
    margin = max(2, min(h, w) // 6)
    strips = [
        gray[:margin, :].ravel(),
        gray[-margin:, :].ravel(),
        gray[:, :margin].ravel(),
        gray[:, -margin:].ravel(),
    ]
    bg = float(np.median(np.concatenate(strips)))
    flat = gray.astype(np.float32) - bg + 128.0
    return np.clip(flat, 0, 255).astype(np.uint8)


def norm_contrast(gray):
    """Chuẩn hoá độ tương phản cục bộ — bớt phụ thuộc độ sáng nền."""
    if gray is None or gray.size == 0 or np is None:
        return gray
    g = gray.astype(np.float32)
    g -= float(g.mean())
    std = float(g.std())
    if std > 1e-3:
        g = (g / std) * 32.0 + 128.0
    return np.clip(g, 0, 255).astype(np.uint8)


def silhouette(gray):
    """Mask hình dạng icon (Otsu) — khớp theo silhouette, ít bị nhiễu màu nền."""
    g = norm_contrast(gray)
    _, bw = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return bw


def edge(gray):
    """Độ lớn gradient (Sobel) — đặc trưng theo biên, ổn định hơn cường độ thô."""
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    m = cv2.magnitude(gx, gy)
    m = cv2.normalize(m, None, 0, 255, cv2.NORM_MINMAX)
    return m.astype("uint8")


def isolate_icon(gray):
    """Tách icon khỏi nền ô; giữ thành phần liên thông lớn nhất."""
    if gray is None or gray.size == 0 or np is None or cv2 is None:
        return gray
    h, w = gray.shape[:2]
    if h < 5 or w < 5:
        return gray

    flat = flatten_background(gray)
    border = np.concatenate([flat[0, :], flat[-1, :], flat[:, 0], flat[:, -1]])
    bg = float(np.median(border))
    diff = np.abs(flat.astype(np.int16) - int(round(bg)))
    thresh = max(8.0, float(diff.std()) * 0.38)
    mask = (diff > thresh).astype(np.uint8) * 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=1)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)

    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cnts:
        return flat
    largest = max(cnts, key=cv2.contourArea)
    if cv2.contourArea(largest) < 0.08 * h * w:
        return flat
    x, y, bw, bh = cv2.boundingRect(largest)
    pad = 1
    y0 = max(0, y - pad)
    x0 = max(0, x - pad)
    y1 = min(h, y + bh + pad)
    x1 = min(w, x + bw + pad)
    return flat[y0:y1, x0:x1]


def prep_icon(gray, size=64, trim=0.12):
    """Cắt sát icon -> chuẩn hoá kích thước -> bỏ viền nền còn sót."""
    icon = isolate_icon(gray)
    g = cv2.resize(icon, (size, size), interpolation=cv2.INTER_AREA)
    g = norm_contrast(g)
    m = int(size * trim)
    return g[m:size - m, m:size - m]


def passes_threshold(threshold, score, ranked_scores, margin=MATCH_MARGIN, floor=MATCH_FLOOR):
    """Đạt ngưỡng thường HOẶC ứng viên #1 vượt trội rõ so với #2."""
    if score >= threshold:
        return True
    second = ranked_scores[1] if len(ranked_scores) > 1 else 0.0
    return score >= floor and (score - second) >= margin
