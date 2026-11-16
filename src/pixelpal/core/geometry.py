"""Small geometry helpers shared by the pure-Python core."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def center_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def center_y(self) -> float:
        return (self.top + self.bottom) / 2

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and self.top <= y <= self.bottom

    def covers(self, other: "Rect", slack: float = 0.0) -> bool:
        return (self.left <= other.left + slack and self.top <= other.top + slack
                and self.right >= other.right - slack and self.bottom >= other.bottom - slack)

    def is_empty(self) -> bool:
        return self.width <= 0 or self.height <= 0


Interval = tuple[float, float]


def subtract_intervals(base: Interval, cuts: list[Interval], min_len: float = 0.0) -> list[Interval]:
    """Return the parts of ``base`` not covered by any interval in ``cuts``."""
    pieces = [base]
    for c1, c2 in cuts:
        nxt: list[Interval] = []
        for a, b in pieces:
            if c2 <= a or c1 >= b:
                nxt.append((a, b))
                continue
            if c1 > a:
                nxt.append((a, c1))
            if c2 < b:
                nxt.append((c2, b))
        pieces = nxt
    return [(a, b) for a, b in pieces if b - a > min_len]


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v
