"""A small pixel-style speech bubble that floats above the pet and never takes input."""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QWidget

INK = QColor(59, 42, 63)
PAPER = QColor(255, 252, 240)
PAD, STEP, TAIL, MAX_TEXT_W = 9, 3, 9, 210


class SpeechBubble(QWidget):
    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint
                         | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint
                         | Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowTransparentForInput)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        font = QFont()
        font.setPointSizeF(9.5)
        font.setBold(True)
        self.setFont(font)
        self.text = ""
        self._tail_x = 0
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.hide)

    def say(self, text: str, seconds: float) -> None:
        self.text = text
        box = QFontMetrics(self.font()).boundingRect(
            QRect(0, 0, MAX_TEXT_W, 1000), int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), text)
        self.resize(max(40, box.width() + 2 * PAD + 2), box.height() + 2 * PAD + TAIL)
        self._hide.start(int(seconds * 1000))
        self.update()

    def place(self, head_x: int, head_y: int, bounds: QRect) -> None:
        """Sit above the point (head_x, head_y) but stay inside the screen ``bounds``."""
        x = max(bounds.left() + 2, min(head_x - self.width() // 2, bounds.right() - self.width() - 2))
        y = max(bounds.top() + 2, head_y - self.height())
        tail = max(STEP * 3, min(head_x - x, self.width() - STEP * 3))
        if tail != self._tail_x:
            self._tail_x = tail
            self.update()
        if self.x() != x or self.y() != y:
            self.move(x, y)

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        w, h = self.width(), self.height() - TAIL
        # stepped corners instead of curves, so it reads as pixel art
        for colour, inset in ((INK, 0), (PAPER, STEP)):
            p.fillRect(inset + STEP, inset, w - 2 * (inset + STEP), h - 2 * inset, colour)
            p.fillRect(inset, inset + STEP, w - 2 * inset, h - 2 * (inset + STEP), colour)
        for i in range(TAIL // STEP):
            half = (TAIL // STEP - i) * STEP
            p.fillRect(self._tail_x - half, h + i * STEP - STEP, 2 * half, STEP, INK)
            if half > STEP:
                p.fillRect(self._tail_x - half + STEP, h + i * STEP - 2 * STEP, 2 * (half - STEP), STEP, PAPER)
        p.setPen(INK)
        p.drawText(QRect(PAD + 1, PAD, w - 2 * PAD, h - 2 * PAD),
                   int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft), self.text)
        p.end()
