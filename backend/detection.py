# -*- coding: utf-8 -*-
"""
DetectionController: chạy nhận diện súng ở thread nền.

Tab mở/đóng balo xen kẽ:
  - Tab nhận diện thành công (thấy tên súng) -> Tab kế tiếp BỎ QUA (đóng balo).
  - Tab sau đó lại nhận diện bình thường (mở balo).
Không delay — chụp ngay khi bấm Tab.
"""

import threading


class DetectionController(threading.Thread):
    def __init__(self, detector, apply_fn):
        super().__init__(daemon=True)
        self.detector = detector
        self.apply_fn = apply_fn      # apply_fn(result) -> True nếu áp dụng được
        self._event = threading.Event()
        self._running = True
        self._skip_next = False       # Tab kế tiếp bỏ qua sau lần nhận diện OK

    def trigger(self):
        """Yêu cầu nhận diện (gọi từ engine khi bấm Tab)."""
        if self._skip_next:
            self._skip_next = False
            return
        self._event.set()

    def reset_tab_cycle(self):
        """Reset chu kỳ Tab (vd tắt/bật lại auto-detect)."""
        self._skip_next = False

    def stop(self):
        self._running = False
        self._event.set()

    def detect_once(self):
        """Nhận diện đồng bộ — luôn chạy, không áp dụng chu kỳ Tab (nút test)."""
        result = self.detector.detect()
        if self.apply_fn:
            self.apply_fn(result)
        return result

    def run(self):
        while self._running:
            self._event.wait()
            self._event.clear()
            if not self._running:
                break
            try:
                result = self.detector.detect()
                if self.apply_fn:
                    ok = self.apply_fn(result)
                    if ok:
                        self._skip_next = True
            except Exception:
                pass
