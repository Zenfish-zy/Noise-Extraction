"""波形控件：绘制整段波形概览，叠加事件高亮，支持点击定位与播放游标。

设计要点（KISS）:
  - 不画全部采样点（几千万个），预先下采样成"每像素列的 min/max 包络"，
    重绘极快。
  - 事件用半透明色块叠加，被选中的事件描边高亮。
  - 点击 → 发 seek 信号(秒)；外部播放进度 → setCursor(秒) 触发重绘游标。
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPen
from PySide6.QtWidgets import QWidget

from ..detect import NoiseEvent

# 事件类型 → 颜色（淡雅低饱和，与浅色主题协调）
KIND_COLORS = {
    "rumble": QColor(79, 126, 110),     # 竹青：低频闷响
    "thud": QColor(176, 123, 82),       # 赭石：重击
    "drag": QColor(122, 109, 148),      # 黛紫：拖拽
    "transient": QColor(106, 142, 122),  # 青灰绿：瞬态
    "other": QColor(150, 142, 126),     # 暖灰
}
_BG = QColor(251, 250, 246)            # 月白
_WAVE = QColor(150, 142, 126)          # 墨灰波形
_CURSOR = QColor(176, 91, 74)          # 朱赭游标
_SUSPECT_HATCH = QColor(176, 91, 74, 70)
_SELECTION = QColor(79, 126, 110, 45)
_SELECTION_BORDER = QColor(79, 126, 110)


class WaveformView(QWidget):
    seeked = Signal(float)          # 用户点击 → 目标秒
    span_selected = Signal(float, float)  # 拖拽框选 → (起始秒, 结束秒)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(160)
        self.setMouseTracking(True)
        self._env_min = np.zeros(0, dtype=np.float32)
        self._env_max = np.zeros(0, dtype=np.float32)
        self._duration = 0.0
        self._events: list[NoiseEvent] = []
        self._selected = -1
        self._cursor_sec = 0.0
        self._cached_width = 0
        # 框选状态：按住拖拽即进入框选模式
        self._select_mode = False        # True 时左键拖拽=框选新增事件，否则=定位
        self._drag_x0 = -1.0             # 拖拽起点（像素）
        self._drag_x1 = -1.0             # 拖拽当前点（像素）
        self._dragging = False

    # ---- 外部接口 ----
    def set_audio(self, data: np.ndarray, sr: int) -> None:
        self._duration = len(data) / sr if sr else 0.0
        self._raw = data
        self._sr = sr
        self._cached_width = 0  # 强制重算包络
        self._rebuild_envelope()
        self.update()

    def set_events(self, events: list[NoiseEvent]) -> None:
        self._events = events
        self.update()

    def set_selected(self, index: int) -> None:
        self._selected = index
        self.update()

    def set_cursor(self, sec: float) -> None:
        self._cursor_sec = sec
        self.update()

    def set_select_mode(self, on: bool) -> None:
        """开启/关闭「框选新增事件」模式。开启时左键拖拽=框选区间。"""
        self._select_mode = on
        self._dragging = False
        self._drag_x0 = self._drag_x1 = -1.0
        self.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)
        self.update()

    # ---- 包络下采样 ----
    def _rebuild_envelope(self) -> None:
        w = max(1, self.width())
        if w == self._cached_width or not hasattr(self, "_raw"):
            return
        n = len(self._raw)
        if n == 0:
            self._env_min = np.zeros(w, dtype=np.float32)
            self._env_max = np.zeros(w, dtype=np.float32)
            self._cached_width = w
            return
        # 每列取一段的 min/max
        idx = np.linspace(0, n, w + 1).astype(np.int64)
        emin = np.empty(w, dtype=np.float32)
        emax = np.empty(w, dtype=np.float32)
        for i in range(w):
            a, b = idx[i], idx[i + 1]
            if b <= a:
                emin[i] = emax[i] = 0.0
            else:
                seg = self._raw[a:b]
                emin[i] = seg.min()
                emax[i] = seg.max()
        self._env_min, self._env_max = emin, emax
        self._cached_width = w

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._cached_width = 0
        self._rebuild_envelope()
        super().resizeEvent(event)

    # ---- 绘制 ----
    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        mid = h / 2
        p.fillRect(self.rect(), _BG)

        if self._duration <= 0:
            p.setPen(QColor(150, 142, 126))
            p.drawText(self.rect(), Qt.AlignCenter, "导入录音后在此显示波形")
            return

        self._rebuild_envelope()

        # 事件高亮块（先画，作为背景）
        for i, ev in enumerate(self._events):
            x0 = ev.start / self._duration * w
            x1 = ev.end / self._duration * w
            rect = QRectF(x0, 0, max(2.0, x1 - x0), h)
            col = QColor(KIND_COLORS.get(ev.kind, KIND_COLORS["other"]))
            col.setAlpha(70 if ev.keep else 25)
            p.fillRect(rect, col)
            if ev.suspect_self:
                p.fillRect(rect, _SUSPECT_HATCH)
            if i == self._selected:
                p.setPen(QPen(QColor(52, 49, 43), 2))
                p.drawRect(rect)

        # 波形包络
        p.setPen(QPen(_WAVE, 1))
        scale = mid * 0.92
        for x in range(min(w, len(self._env_min))):
            y0 = mid - self._env_max[x] * scale
            y1 = mid - self._env_min[x] * scale
            p.drawLine(x, int(y0), x, int(y1))

        # 播放游标
        cx = self._cursor_sec / self._duration * w
        p.setPen(QPen(_CURSOR, 2))
        p.drawLine(int(cx), 0, int(cx), h)

        if self._dragging and self._drag_x0 >= 0 and self._drag_x1 >= 0:
            x0, x1 = sorted((self._drag_x0, self._drag_x1))
            rect = QRectF(x0, 0, max(2.0, x1 - x0), h)
            p.fillRect(rect, _SELECTION)
            p.setPen(QPen(_SELECTION_BORDER, 2))
            p.drawRect(rect)

    def _x_to_sec(self, x: float) -> float:
        if self._duration <= 0 or self.width() <= 0:
            return 0.0
        return max(0.0, min(self._duration, x / self.width() * self._duration))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._duration > 0 and event.button() == Qt.LeftButton:
            x = float(event.position().x())
            if self._select_mode:
                self._dragging = True
                self._drag_x0 = self._drag_x1 = max(0.0, min(self.width(), x))
                self.update()
            else:
                self.seeked.emit(self._x_to_sec(x))
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._dragging and self._select_mode:
            x = float(event.position().x())
            self._drag_x1 = max(0.0, min(self.width(), x))
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if (
            self._duration > 0
            and self._dragging
            and self._select_mode
            and event.button() == Qt.LeftButton
        ):
            self._drag_x1 = max(0.0, min(self.width(), float(event.position().x())))
            x0, x1 = sorted((self._drag_x0, self._drag_x1))
            self._dragging = False
            self._drag_x0 = self._drag_x1 = -1.0
            self.update()
            if abs(x1 - x0) >= 4:
                start = self._x_to_sec(x0)
                end = self._x_to_sec(x1)
                if end - start >= 0.03:
                    self.span_selected.emit(start, end)
            event.accept()
            return
        super().mouseReleaseEvent(event)
