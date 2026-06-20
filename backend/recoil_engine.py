# -*- coding: utf-8 -*-
"""
Engine giảm giật:
- Chạy 1 thread nền, poll trạng thái nút chuột bằng GetAsyncKeyState (Windows).
- Khi đang bắn (giữ chuột trái, tuỳ chọn yêu cầu giữ chuột phải/ADS),
  liên tục đẩy chuột XUỐNG (và bù ngang) theo profile của ô súng đang chọn.
- Phím 1 / 2 chuyển ô súng đang active (giống PUBG đổi súng chính/phụ).
- Di chuyển mượt: chia nhỏ theo từng tick (~6ms) thay vì giật từng phát.

Movement dùng ctypes SendInput (relative move) cho mượt và nhanh.

Macro CCW (slide khi chạy):
- Bật CCW, bấm Shift trước rồi W; W trước Shift thì không chạy CCW.
"""

import ctypes
import threading
import time

# --- ctypes SendInput ---------------------------------------------------------
SendInput = ctypes.windll.user32.SendInput
GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

PUL = ctypes.POINTER(ctypes.c_ulong)


class _MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class _KeyboardInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class _InputI(ctypes.Union):
    _fields_ = [("mi", _MouseInput),
                ("ki", _KeyboardInput)]


class _Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("ii", _InputI)]


MOUSEEVENTF_MOVE = 0x0001
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002

VK_LBUTTON = 0x01
VK_RBUTTON = 0x02
VK_1 = 0x31
VK_2 = 0x32
VK_F8 = 0x77  # phím bật/tắt nhanh
VK_DELETE = 0x2E  # phím bật/tắt overlay (Del)
VK_F9 = 0x78
VK_F10 = 0x79  # phím chụp + vẽ overlay các ô phụ kiện (kiểm tra vị trí)
VK_TAB = 0x09  # phím mở balo -> kích hoạt nhận diện
VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_W = 0x57
VK_C = 0x43
CCW_HOLD_STABLE = 0.12   # giây: cả 2 phím phải giữ ổn định trước khi tính thời gian chờ
# timing trượt — tap C nhanh; gap C1→C2 ngắn để trượt (dài quá = đứng lên)
CCW_AFTER_W_UP = 0.130     # nghỉ sau ngắt W, trước C1
CCW_C_TAP = 0.038          # mỗi lần bấm C (ngắn, không giữ lâu)
CCW_C_GAP = 0.062          # giữa C1 và C2 (quan trọng — dài = ngồi rồi đứng)
CCW_BEFORE_W = 0.050
CCW_HOLD_W_AFTER = 0.100


def _move_rel(dx, dy):
    extra = ctypes.c_ulong(0)
    mi = _MouseInput(int(dx), int(dy), 0, MOUSEEVENTF_MOVE, 0, ctypes.pointer(extra))
    inp = _Input(INPUT_MOUSE, _InputI(mi=mi))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _send_vk(vk, down=True):
    """Gửi phím qua SendInput (ổn định hơn pyautogui trong game)."""
    extra = ctypes.c_ulong(0)
    flags = 0 if down else KEYEVENTF_KEYUP
    ki = _KeyboardInput(int(vk), 0, flags, 0, ctypes.pointer(extra))
    inp = _Input(INPUT_KEYBOARD, _InputI(ki=ki))
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


def _key_down(vk):
    return GetAsyncKeyState(vk) & 0x8000 != 0


def _shift_held():
    return _key_down(VK_SHIFT) or _key_down(VK_LSHIFT) or _key_down(VK_RSHIFT)


def _ccw_sprint_held():
    return _shift_held() and _key_down(VK_W)


def _ccw_hold_w_up(duration):
    """Ngắt W và giữ ngắt trong khoảng nghỉ (kể cả khi vẫn giữ phím W vật lý)."""
    _send_vk(VK_W, False)
    end = time.perf_counter() + duration
    while time.perf_counter() < end:
        if _key_down(VK_W):
            _send_vk(VK_W, False)
        time.sleep(0.010)


def _ccw_hold_w_down(was_holding=False):
    """Sau CC: bấm và giữ W lại trong game nếu người chơi vẫn giữ phím."""
    if not was_holding and not _key_down(VK_W):
        return
    time.sleep(0.025)
    end = time.perf_counter() + CCW_HOLD_W_AFTER
    while time.perf_counter() < end:
        if _key_down(VK_W):
            _send_vk(VK_W, True)
        else:
            break
        time.sleep(0.010)


def _ccw_tap_c():
    """Bấm C ngắn (tap) — tránh ngồi lâu rồi C2 thành đứng lên."""
    _send_vk(VK_C, True)
    time.sleep(CCW_C_TAP)
    _send_vk(VK_C, False)


class EngineState:
    """Trạng thái chia sẻ giữa giao diện (Api) và thread engine."""

    def __init__(self):
        self.lock = threading.Lock()
        self.enabled = True
        self.require_ads = True       # chỉ kéo khi giữ chuột phải (ngắm)
        self.hipfire_mult = 0.5       # hệ số khi bắn KHÔNG ngắm (chỉ áp dụng nếu require_ads = False)
        self.active_slot = 0          # 0 hoặc 1
        self.auto_detect = False      # bật nhận diện súng khi bấm phím detect
        self.overlay_visible = False  # thanh overlay dưới màn hình đang hiện?
        self.debug_boxes_visible = False  # lớp vẽ các ô cắt nhận diện (F10)
        # phím nóng (VK code)
        self.vk_slot1 = VK_1
        self.vk_slot2 = VK_2
        self.vk_toggle = VK_F8
        self.vk_overlay = VK_DELETE
        self.vk_boxes = VK_F10
        self.vk_detect = VK_TAB
        # macro CCW — bật trong setting, giữ Shift+W sẽ tự trượt
        self.ccw_enabled = False
        self.ccw_cooldown = 2.0     # giây nghỉ giữa mỗi lần trượt
        # mỗi slot: {'name', 'shots_per_sec', 'phase_pulls':[..], 'phase_bounds':[..]} hoặc None
        self.slots = [None, None]

    def snapshot(self):
        with self.lock:
            return {
                "enabled": self.enabled,
                "require_ads": self.require_ads,
                "hipfire_mult": self.hipfire_mult,
                "active_slot": self.active_slot,
                "auto_detect": self.auto_detect,
                "overlay_visible": self.overlay_visible,
                "debug_boxes_visible": self.debug_boxes_visible,
                "vk_slot1": self.vk_slot1,
                "vk_slot2": self.vk_slot2,
                "vk_toggle": self.vk_toggle,
                "vk_overlay": self.vk_overlay,
                "vk_boxes": self.vk_boxes,
                "vk_detect": self.vk_detect,
                "ccw_enabled": self.ccw_enabled,
                "ccw_cooldown": self.ccw_cooldown,
                "slots": list(self.slots),
            }


class RecoilEngine(threading.Thread):
    TICK = 0.006  # ~166 Hz

    def __init__(self, state: EngineState):
        super().__init__(daemon=True)
        self.state = state
        self._running = True
        self._acc_y = 0.0
        self._shots = 0.0   # số viên đã bắn từ lúc bóp cò (để chọn giai đoạn)
        self._f8_prev = False
        self._overlay_prev = False
        self._boxes_prev = False
        self._detect_prev = False
        self._ccw_both_since = None
        self._ccw_sliding = False
        self._ccw_had_w_alone = False
        self._ccw_w_before_shift = False
        self.on_detect = None       # callback() khi bấm phím detect (vd Tab)
        self.on_show_boxes = None   # callback() khi bấm phím F10 (vẽ ô phụ kiện)

    def stop(self):
        self._running = False

    def _ccw_track_order(self):
        """Chỉ CCW khi Shift trước W; W trước Shift thì bỏ qua."""
        w = _key_down(VK_W)
        sh = _shift_held()
        if not w:
            self._ccw_had_w_alone = False
            self._ccw_w_before_shift = False
        elif w and not sh:
            self._ccw_had_w_alone = True
        elif w and sh and self._ccw_had_w_alone:
            self._ccw_w_before_shift = True

    def _ccw_slide_sequence(self):
        """Ngắt W → tap C → tap C → giữ W lại (Shift do người chơi giữ)."""
        if self._ccw_sliding:
            return False
        self._ccw_sliding = True
        was_holding_w = _key_down(VK_W)

        def _work():
            try:
                _ccw_hold_w_up(CCW_AFTER_W_UP)
                _ccw_tap_c()
                time.sleep(CCW_C_GAP)
                _ccw_tap_c()
                time.sleep(CCW_BEFORE_W)
                _ccw_hold_w_down(was_holding_w)
            finally:
                self._ccw_sliding = False

        threading.Thread(target=_work, daemon=True).start()
        return True

    def _ccw_tick(self, now, ccw_enabled, ccw_cooldown):
        """CCW: Shift trước rồi W, giữ đủ cooldown."""
        self._ccw_track_order()
        both = _ccw_sprint_held()

        if not ccw_enabled or not both:
            self._ccw_both_since = None
            return

        if self._ccw_w_before_shift:
            self._ccw_both_since = None
            return

        if self._ccw_both_since is None:
            self._ccw_both_since = now
            return

        held = now - self._ccw_both_since
        if held < CCW_HOLD_STABLE:
            return
        if self._ccw_sliding or held < ccw_cooldown:
            return

        if self._ccw_slide_sequence():
            self._ccw_both_since = now

    def run(self):
        last = time.perf_counter()
        while self._running:
            now = time.perf_counter()
            dt = now - last
            last = now

            with self.state.lock:
                enabled = self.state.enabled
                require_ads = self.state.require_ads
                hipfire_mult = self.state.hipfire_mult
                active = self.state.active_slot
                profile = self.state.slots[active]
                vk_slot1 = self.state.vk_slot1
                vk_slot2 = self.state.vk_slot2
                vk_toggle = self.state.vk_toggle
                vk_overlay = self.state.vk_overlay

                # phím đổi ô súng
                if _key_down(vk_slot1):
                    self.state.active_slot = 0
                elif _key_down(vk_slot2):
                    self.state.active_slot = 1

                # phím bật/tắt (chỉ kích hoạt 1 lần mỗi lần nhấn)
                tgl = _key_down(vk_toggle)
                if tgl and not self._f8_prev:
                    self.state.enabled = not self.state.enabled
                    enabled = self.state.enabled
                self._f8_prev = tgl

                # phím bật/tắt overlay (edge)
                ov = _key_down(vk_overlay)
                if ov and not self._overlay_prev:
                    self.state.overlay_visible = not self.state.overlay_visible
                self._overlay_prev = ov

                # phím F10 -> bật/tắt lớp vẽ ô cắt nhận diện (edge)
                bxk = _key_down(self.state.vk_boxes)
                if bxk and not self._boxes_prev:
                    self.state.debug_boxes_visible = not self.state.debug_boxes_visible
                self._boxes_prev = bxk

                auto_detect = self.state.auto_detect
                vk_detect = self.state.vk_detect
                ccw_enabled = self.state.ccw_enabled
                ccw_cooldown = self.state.ccw_cooldown

            self._ccw_tick(now, ccw_enabled, ccw_cooldown)

            # phím nhận diện (vd Tab) -> gọi callback (không chặn luồng kéo)
            det = _key_down(vk_detect)
            if det and not self._detect_prev and auto_detect and self.on_detect:
                try:
                    self.on_detect()
                except Exception:
                    pass
            self._detect_prev = det

            firing = False
            ads = False
            if enabled and profile:
                lmb = _key_down(VK_LBUTTON)
                rmb = _key_down(VK_RBUTTON)
                ads = rmb
                firing = lmb and (rmb or not require_ads)

            if firing:
                sps = profile["shots_per_sec"]
                self._shots += sps * dt

                # chọn lực kéo theo giai đoạn băng đạn hiện tại
                bounds = profile["phase_bounds"]
                pulls = profile["phase_pulls"]
                idx = len(bounds)
                for i, b in enumerate(bounds):
                    if self._shots < b:
                        idx = i
                        break
                pull = pulls[idx] if idx < len(pulls) else pulls[-1]

                scale = 1.0 if ads else hipfire_mult
                self._acc_y += pull * scale * dt
                move_y = int(self._acc_y)
                if move_y:
                    _move_rel(0, move_y)  # chỉ kéo dọc
                    self._acc_y -= move_y
            else:
                self._acc_y = 0.0
                self._shots = 0.0   # nhả cò -> reset về giai đoạn đầu

            time.sleep(self.TICK)
