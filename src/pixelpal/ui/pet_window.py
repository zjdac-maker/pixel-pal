"""The pet itself: a frameless, transparent, always-on-top window the size of one sprite."""
from __future__ import annotations

import time

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

DRAG_THRESHOLD = 5


class PetWindow(QWidget):
    grabbed = Signal(QPoint)            # global cursor position
    dragged = Signal(QPoint)
    released = Signal(float, float)     # throw velocity in px/s
    petted = Signal()
    menu_requested = Signal(QPoint)

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus)
        # Per-pixel transparency. On Windows this makes a layered window, where fully
        # transparent pixels do not receive mouse input: clicks beside the pet go through.
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._pixmap: QPixmap | None = None
        self._press: QPoint | None = None
        self._dragging = False
        self._trail: list[tuple[float, QPoint]] = []

    def set_pixmap(self, pixmap: QPixmap) -> None:
        if pixmap is not self._pixmap:
            self._pixmap = pixmap
            self.update()

    def paintEvent(self, _event) -> None:
        if self._pixmap is not None:
            painter = QPainter(self)
            painter.drawPixmap(0, 0, self._pixmap)
            painter.end()

    # -- mouse ------------------------------------------------------------------------------
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._dragging = False
            self._trail = [(time.monotonic(), self._press)]
        elif event.button() == Qt.MouseButton.RightButton:
            self.menu_requested.emit(event.globalPosition().toPoint())

    def mouseMoveEvent(self, event) -> None:
        if self._press is None:
            return
        pos = event.globalPosition().toPoint()
        if not self._dragging and (pos - self._press).manhattanLength() >= DRAG_THRESHOLD:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.grabbed.emit(self._press)
        if self._dragging:
            self._trail.append((time.monotonic(), pos))
            del self._trail[:-6]
            self.dragged.emit(pos)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._press is None:
            return
        self._press = None
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        if not self._dragging:
            self.petted.emit()
            return
        self._dragging = False
        vx = vy = 0.0
        now = time.monotonic()
        recent = [(t, p) for t, p in self._trail if now - t < 0.12]
        if len(recent) >= 2:
            (t0, p0), (t1, p1) = recent[0], recent[-1]
            if t1 > t0:
                vx, vy = (p1.x() - p0.x()) / (t1 - t0), (p1.y() - p0.y()) / (t1 - t0)
        self.released.emit(vx, vy)
