# -*- coding: utf-8 -*-
"""
Overlay in-game: một THANH NGANG bo góc, mờ ở đáy màn hình hiển thị súng +
phụ kiện đang dùng, để xem trực tiếp khi chơi mà không cần Alt-Tab sang app.

Đặc điểm (Windows):
- Luôn nổi trên cùng (topmost), không khung, không hiện ở taskbar.
- Click-through: chuột bấm xuyên qua overlay, KHÔNG ăn input của game.
- Nền tối trong suốt một phần; ô súng đang active có viền hồng nổi bật.
- Vẽ bằng Canvas: thanh bo góc + thẻ súng + "chip" phụ kiện cho gọn đẹp.

Chạy ở thread riêng với vòng lặp tkinter riêng. Engine chỉ bật/tắt cờ
overlay_visible; overlay tự đọc dữ liệu qua data_provider() mỗi nhịp.

Lưu ý: overlay hoạt động khi game ở Borderless/Windowed (giống điều kiện để
macro SendInput ăn). Fullscreen độc quyền (exclusive) sẽ không hiện overlay.
"""

import threading

try:
    import tkinter as tk
    import tkinter.font as tkfont
except Exception:
    tk = None

try:
    import ctypes
    _user32 = ctypes.windll.user32
except Exception:
    _user32 = None

# ---- hằng số Win32 cho click-through / ẩn taskbar ----
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_NOACTIVATE = 0x08000000

# ---- bảng màu (dark hack × anime neon — khớp web/style.css) ----
TRANSPARENT_KEY = "#ff00ff"      # màu "tàng hình" (vùng ngoài thanh)
BAR_BG = "#060608"               # đen trong
BAR_LINE = "#3a3528"             # viền vàng đồng mờ
GLOSS = "#12121a"                # vạch gloss đỉnh (tím đen)
ACCENT = "#ffe566"               # vàng neon — tên súng
ACCENT_GLOW = "#ff4fd8"          # viền hồng khi bật
CYAN = "#00f5ff"
GREEN = "#39ff14"                # hacker green
GRAY = "#4a4638"
TXT = "#f5e8b8"                  # chữ vàng nhạt
TXT_DIM = "#a89868"
CHIP_BG = "#0a0a0e"
CHIP_LINE = "#3a3528"
CHIP_TXT = "#f5e8b8"
SCOPE_CHIP_BG = "#100e18"
SCOPE_CHIP_LINE = "#b44aff"
SCOPE_CHIP_TXT = "#ff8ae8"
EDITOR_BG = "#060608"
EDITOR_TAB_FG = "#060608"

# ---- màu khung debug (F10) theo từng loại ô ----
DBG_ALPHA = 0.88
KIND_COLORS = {
    "name":   "#00f5ff",   # tên súng — cyan
    "scope":  "#ff4fd8",   # scope — hồng
    "scan":   "#3a3528",   # vùng quét scope (mờ)
    "muzzle": "#39ff14",   # họng — xanh hack
    "grip":   "#ffe566",   # grip — vàng
    "mag":    "#ff9d5c",   # băng đạn — cam
    "stock":  "#b44aff",   # báng — tím
}
DBG_DEFAULT = "#f5e8b8"


class Overlay(threading.Thread):
    ALPHA = 0.72          # trong hơn — nền game lộ rõ (dark glass)
    PAD = 10
    H = 32                # cao hơn chút để chữ đọc rõ
    BOTTOM_GAP = 0        # sát đáy màn hình hẳn

    def __init__(self, data_provider, save_provider=None):
        super().__init__(daemon=True)
        self.data_provider = data_provider
        self.save_provider = save_provider   # callback(list_box) khi thoát chế độ chỉnh
        self._running = True
        self.root = None
        self.canvas = None
        self._mapped = False
        self._sig = None
        self._geom = None
        # cửa sổ EDITOR kéo-thả các ô cắt (F10)
        self.dbg = None
        self.dbg_canvas = None
        self._dbg_mapped = False
        self.edit_boxes = None     # list dict {key,label,kind,x,y,w,h}
        self._drag = None          # (box, mode, ox, oy)
        self._active = None

    def stop(self):
        self._running = False
        try:
            if self.root is not None:
                self.root.after(0, self.root.destroy)
        except Exception:
            pass

    # ---------------- vòng đời tkinter ----------------
    def run(self):
        if tk is None:
            return
        try:
            self._build()
            self.root.mainloop()
        except Exception:
            pass

    def _build(self):
        self.root = tk.Tk()
        self.root.title("VVIP_PUBG_OVERLAY")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        try:
            self.root.attributes("-alpha", self.ALPHA)
            self.root.attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            pass
        self.root.configure(bg=TRANSPARENT_KEY)

        self.f_name = tkfont.Font(family="Consolas", size=10, weight="bold")
        self.f_type = tkfont.Font(family="Consolas", size=8, weight="bold")
        self.f_chip = tkfont.Font(family="Consolas", size=8, weight="bold")
        self.f_badge = tkfont.Font(family="Consolas", size=8, weight="bold")
        self.f_status = tkfont.Font(family="Consolas", size=8, weight="bold")

        self.sw = self.root.winfo_screenwidth()
        self.sh = self.root.winfo_screenheight()
        self.maxw = min(self.sw - 40, 1500)

        self.canvas = tk.Canvas(self.root, bg=TRANSPARENT_KEY,
                                highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)

        self.root.geometry(f"{self.maxw}x{self.H}+20+{self.sh - self.H - self.BOTTOM_GAP}")
        self.root.update_idletasks()
        self._make_clickthrough(self.root)
        self.root.withdraw()

        self._build_debug()
        self._tick()

    def _build_debug(self):
        """Cửa sổ EDITOR phủ toàn màn hình: kéo-thả + resize các ô cắt (F10).

        Nền dùng transparentcolor nên game vẫn nhìn rõ; chỉ các 'tab nhãn' và
        'núm góc' là đặc (bắt được chuột) -> kéo tab = di chuyển, kéo núm = resize.
        KHÔNG đặt click-through cho cửa sổ này để nhận sự kiện chuột.
        """
        self.f_box = tkfont.Font(family="Consolas", size=10, weight="bold")
        self.f_hint = tkfont.Font(family="Consolas", size=12, weight="bold")
        self.dbg = tk.Toplevel(self.root)
        self.dbg.overrideredirect(True)
        self.dbg.attributes("-topmost", True)
        try:
            self.dbg.attributes("-alpha", 0.92)
            self.dbg.attributes("-transparentcolor", TRANSPARENT_KEY)
        except Exception:
            pass
        self.dbg.configure(bg=TRANSPARENT_KEY)
        self.dbg_canvas = tk.Canvas(self.dbg, bg=TRANSPARENT_KEY,
                                    highlightthickness=0, bd=0)
        self.dbg_canvas.pack(fill="both", expand=True)
        self.dbg.geometry(f"{self.sw}x{self.sh}+0+0")
        self.dbg.update_idletasks()
        self.dbg_canvas.bind("<ButtonPress-1>", self._ed_press)
        self.dbg_canvas.bind("<B1-Motion>", self._ed_drag)
        self.dbg_canvas.bind("<ButtonRelease-1>", self._ed_release)
        self.dbg.withdraw()

    # ---------------- Win32 ----------------
    def _hwnd_of(self, win):
        if _user32 is None or win is None:
            return None
        try:
            wid = win.winfo_id()
            parent = _user32.GetParent(wid)
            return parent if parent else wid
        except Exception:
            return None

    def _make_clickthrough(self, win):
        hwnd = self._hwnd_of(win)
        if _user32 is None or not hwnd:
            return
        try:
            ex = _user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
            ex |= (WS_EX_LAYERED | WS_EX_TRANSPARENT
                   | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
            _user32.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        except Exception:
            pass

    # ---------------- helpers vẽ ----------------
    @staticmethod
    def _round_rect(c, x1, y1, x2, y2, r, **kw):
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
               x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
               x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return c.create_polygon(pts, smooth=True, **kw)

    CHIP_PAD = 6
    CHIP_GAP = 4
    CHIP_H = 16

    def _chip(self, c, x, cy, text, scope=False):
        """Vẽ 1 chip phụ kiện (căn theo TÂM dọc cy), trả về chiều rộng đã dùng."""
        w = self.f_chip.measure(text) + self.CHIP_PAD * 2
        h = self.CHIP_H
        if scope:
            bg, ln, fg = SCOPE_CHIP_BG, SCOPE_CHIP_LINE, SCOPE_CHIP_TXT
        else:
            bg, ln, fg = CHIP_BG, CHIP_LINE, CHIP_TXT
        self._round_rect(c, x, cy - h / 2, x + w, cy + h / 2, h / 2,
                         fill=bg, outline=ln, width=1)
        c.create_text(x + w / 2, cy, text=text, fill=fg, font=self.f_chip)
        return w

    @staticmethod
    def _is_scope_chip(a):
        s = a.lower()
        return ("dot" in s) or ("holo" in s) or ("hybrid" in s) or ("scope" in s) or \
               ("x" in s and a[:1].isdigit())

    def _chip_label(self, a):
        """Chip scope có ký hiệu ◎ cho nổi bật."""
        return ("◎ " + a) if self._is_scope_chip(a) else a

    # ---------------- nội dung ----------------
    def _signature(self, data):
        slots = data.get("slots") or []
        parts = [str(data.get("enabled")), str(data.get("active_slot")),
                 f"{data.get('sensitivity'):.2f}"]
        for s in slots:
            if s:
                parts.append(s.get("name", "") + "|" + ",".join(s.get("atts") or []))
            else:
                parts.append("-")
        return "§".join(parts)

    def _tick(self):
        if not self._running:
            return
        try:
            data = self.data_provider() if self.data_provider else None
        except Exception:
            data = None

        visible = bool(data and data.get("visible"))
        if visible and not self._mapped:
            self.root.deiconify()
            self.root.attributes("-topmost", True)
            self._make_clickthrough(self.root)
            self._mapped = True
            self._sig = None      # ép vẽ lại
        elif not visible and self._mapped:
            self.root.withdraw()
            self._mapped = False

        if visible and data:
            sig = self._signature(data)
            if sig != self._sig:
                self._sig = sig
                self._render(data)
            self.root.attributes("-topmost", True)

        # --- EDITOR kéo-thả các ô cắt (F10) ---
        edit_on = bool(data and data.get("debug_visible"))
        if self.dbg is not None:
            if edit_on and not self._dbg_mapped:
                # vào chế độ chỉnh: nạp ô từ dữ liệu hiện tại
                self.edit_boxes = [
                    {"key": b["key"], "label": b.get("label", ""),
                     "kind": b.get("kind", ""), "x": int(b["x"]), "y": int(b["y"]),
                     "w": int(b["w"]), "h": int(b["h"])}
                    for b in (data.get("boxes") or []) if b.get("key")
                ]
                self._active = None
                self.dbg.deiconify()
                self.dbg.attributes("-topmost", True)
                self.dbg.lift()
                self._dbg_mapped = True
                self._ed_render()
            elif not edit_on and self._dbg_mapped:
                # thoát: LƯU toạ độ rồi ẩn
                self._ed_save()
                self.dbg.withdraw()
                self._dbg_mapped = False
            elif edit_on:
                self.dbg.attributes("-topmost", True)

        try:
            self.root.after(120, self._tick)
        except Exception:
            pass

    # ---------------- EDITOR: lưu + chuột ----------------
    HANDLE = 16

    def _ed_save(self):
        if self.edit_boxes is None or not self.save_provider:
            self.edit_boxes = None
            return
        payload = [{"key": b["key"], "x": int(b["x"]), "y": int(b["y"]),
                    "w": int(b["w"]), "h": int(b["h"])} for b in self.edit_boxes]
        try:
            self.save_provider(payload)
        except Exception:
            pass
        self.edit_boxes = None

    def _ed_hit(self, ex, ey):
        """Trả về (box, mode): mode='resize' nếu trúng núm góc, 'move' nếu trúng tab."""
        H = self.HANDLE
        for b in reversed(self.edit_boxes or []):
            hx, hy = b["x"] + b["w"], b["y"] + b["h"]
            if hx - H <= ex <= hx + 4 and hy - H <= ey <= hy + 4:
                return b, "resize"
        for b in reversed(self.edit_boxes or []):
            tw = self.f_box.measure(b.get("label", "") or "•") + 10
            ty = b["y"] - 17
            if b["x"] <= ex <= b["x"] + tw and ty <= ey <= b["y"]:
                return b, "move"
        return None, None

    def _ed_press(self, e):
        b, mode = self._ed_hit(e.x, e.y)
        if b is None:
            return
        self._active = b
        if mode == "move":
            self._drag = (b, "move", e.x - b["x"], e.y - b["y"])
        else:
            self._drag = (b, "resize", 0, 0)
        self._ed_render()

    def _ed_drag(self, e):
        if not self._drag:
            return
        b, mode, ox, oy = self._drag
        if mode == "move":
            b["x"] = max(0, min(self.sw - b["w"], int(e.x - ox)))
            b["y"] = max(0, min(self.sh - b["h"], int(e.y - oy)))
        else:
            b["w"] = max(16, int(e.x - b["x"]))
            b["h"] = max(16, int(e.y - b["y"]))
        self._ed_render()

    def _ed_release(self, e):
        self._drag = None

    def _ed_render(self):
        c = self.dbg_canvas
        c.delete("all")
        # thanh hướng dẫn ở giữa-trên
        hint = "CHỈNH Ô  ·  kéo NHÃN = di chuyển  ·  kéo NÚM góc ◢ = resize  ·  F10 = LƯU & thoát"
        tw = self.f_hint.measure(hint) + 28
        hx = (self.sw - tw) // 2
        c.create_rectangle(hx, 8, hx + tw, 36, fill=EDITOR_BG, outline=CYAN, width=2)
        c.create_text(self.sw // 2, 22, text=hint, fill=TXT, font=self.f_hint)

        for b in (self.edit_boxes or []):
            x, y, w, h = b["x"], b["y"], b["w"], b["h"]
            col = KIND_COLORS.get(b.get("kind"), DBG_DEFAULT)
            active = (b is self._active)
            # khung (đặc mảnh ở viền; bên trong để trong suốt thấy game)
            c.create_rectangle(x, y, x + w, y + h, outline=col,
                               width=3 if active else 2)
            # tab nhãn (đặc -> kéo để di chuyển)
            label = b.get("label", "") or "•"
            ltw = self.f_box.measure(label) + 10
            c.create_rectangle(x, y - 17, x + ltw, y, fill=col, outline="")
            c.create_text(x + 5, y - 9, anchor="w", text=label,
                          fill=EDITOR_TAB_FG, font=self.f_box)
            # kích thước hiện tại
            c.create_text(x + 4, y + 4, anchor="nw", text=f"{w}×{h}",
                          fill=col, font=self.f_box)
            # núm resize góc dưới-phải (đặc)
            H = self.HANDLE
            c.create_rectangle(x + w - H, y + h - H, x + w, y + h,
                               fill=col, outline=EDITOR_BG)
            c.create_text(x + w - H / 2, y + h - H / 2, text="◢",
                          fill=EDITOR_TAB_FG, font=self.f_box)

    def _content_width(self, data, s, slot_no):
        """Tính bề rộng thanh (chỉ vẽ 1 súng đang cầm)."""
        H = self.H
        sens_txt = f"{float(data.get('sensitivity', 1.0)):.2f}"
        w = self.PAD
        w += H - 14                                   # đèn trạng thái
        w += 6 + self.f_status.measure(sens_txt)      # sens
        w += 12                                       # vạch ngăn + lề
        w += H - 14                                   # badge số slot
        w += 8
        if s:
            w += self.f_name.measure("✦ " + s.get("name", "?"))
            w += 6 + self.f_type.measure(s.get("type", ""))
            chips = s.get("atts") or []
            if chips:
                w += 8
                for a in chips:
                    w += (self.f_chip.measure(self._chip_label(a))
                          + self.CHIP_PAD * 2 + self.CHIP_GAP)
            else:
                w += 8 + self.f_type.measure("— trống —")
        else:
            w += self.f_name.measure("— chưa nhận diện —")
        return int(w + self.PAD)

    def _render(self, data):
        c = self.canvas
        c.delete("all")

        active = data.get("active_slot", 0)
        slots = data.get("slots") or [None, None]
        s = slots[active] if active < len(slots) else None
        slot_no = active + 1
        H = self.H
        cy = H / 2

        total = min(self._content_width(data, s, slot_no), self.maxw)

        # đặt lại kích thước/vị trí cửa sổ nếu đổi (căn giữa, sát đáy)
        x0 = (self.sw - total) // 2
        y0 = self.sh - self.H - self.BOTTOM_GAP
        geom = (total, x0)
        if geom != self._geom:
            self._geom = geom
            self.root.geometry(f"{total}x{self.H}+{x0}+{y0}")
            self.root.update_idletasks()

        on = bool(data.get("enabled"))

        # --- nền thanh: viền glow + thân đen trong + vạch gloss ---
        r = H / 2
        outline = ACCENT_GLOW if on else BAR_LINE
        self._round_rect(c, 1, 1, total - 1, H - 1, r,
                         fill=BAR_BG, outline=outline, width=2)
        if on:
            # viền cyan mờ bên trong (hack glow)
            self._round_rect(c, 3, 3, total - 3, H - 3, r - 2,
                             fill="", outline=CYAN, width=1)
        gh = H * 0.38
        self._round_rect(c, 6, 3, total - 6, 3 + gh, gh / 2,
                         fill=GLOSS, outline="")

        x = self.PAD

        # --- đèn trạng thái (chấm phát sáng) ---
        d = H - 16
        dy = cy - d / 2
        col = GREEN if on else GRAY
        # halo
        self.canvas.create_oval(x - 2, dy - 2, x + d + 2, dy + d + 2,
                                fill="", outline=col)
        self.canvas.create_oval(x, dy, x + d, dy + d, fill=col, outline="")
        x += d + 6

        sens_txt = f"{float(data.get('sensitivity', 1.0)):.2f}"
        c.create_text(x, cy, anchor="w", text=sens_txt,
                      fill=CYAN, font=self.f_status)
        x += self.f_status.measure(sens_txt) + 7

        # --- vạch ngăn ---
        c.create_line(x, 9, x, H - 9, fill=BAR_LINE)
        x += 7

        # --- badge số slot (viên tròn vàng × cyan) ---
        b = H - 14
        by = cy - b / 2
        self._round_rect(c, x, by, x + b, by + b, b / 2,
                         fill=CYAN if on else BAR_LINE, outline=ACCENT if on else "")
        c.create_text(x + b / 2, cy + 0.5, text=str(slot_no),
                      fill=EDITOR_BG, font=self.f_badge)
        x += b + 8

        if s:
            # --- tên súng (✦ vàng neon) ---
            name = f"✦ {s.get('name', '?')}"
            c.create_text(x, cy, anchor="w", text=name, fill=ACCENT,
                          font=self.f_name)
            x += self.f_name.measure(name) + 6
            c.create_text(x, cy + 1, anchor="w", text=s.get("type", ""),
                          fill=TXT_DIM, font=self.f_type)
            x += self.f_type.measure(s.get("type", "")) + 8
            chips = s.get("atts") or []
            if chips:
                for a in chips:
                    sc = self._is_scope_chip(a)
                    used = self._chip(c, x, cy, self._chip_label(a), scope=sc)
                    x += used + self.CHIP_GAP
            else:
                c.create_text(x, cy, anchor="w", text="— trống —",
                              fill=GRAY, font=self.f_type)
        else:
            c.create_text(x, cy, anchor="w", text="— chưa nhận diện —",
                          fill=GRAY, font=self.f_name)
