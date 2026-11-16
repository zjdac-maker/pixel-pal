"""The pet's inner life: a few slow-moving drives that resolve to one visible mood."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .geometry import clamp


class Mood(Enum):
    HAPPY = "happy"
    SLEEPY = "sleepy"
    CURIOUS = "curious"
    EXCITED = "excited"
    CONFUSED = "confused"


# event -> (energy, joy, curiosity, excitement, confusion) deltas
_EVENTS: dict[str, tuple[float, float, float, float, float]] = {
    "petted":        (0.02, 0.20, 0.00, 0.15, -0.20),
    "task_done":     (0.05, 0.25, 0.00, 0.70, -0.30),
    "task_failed":   (0.00, -0.10, 0.00, 0.00, 0.60),
    "thrown":        (0.00, -0.05, 0.00, 0.10, 0.65),
    "lost_surface":  (0.00, 0.00, 0.05, 0.00, 0.45),
    "alert":         (0.05, 0.00, 0.10, 0.30, 0.20),
    "dragged":       (0.02, 0.00, 0.10, 0.10, 0.10),
    "followed":      (0.00, 0.05, -0.50, 0.00, 0.00),
    "explored":      (-0.01, 0.03, -0.02, 0.00, 0.00),
    "looked":        (0.00, 0.00, -0.12, 0.00, 0.00),
    "woke":          (0.10, 0.00, 0.10, 0.00, 0.10),
}


@dataclass
class MoodState:
    energy: float = 0.8
    joy: float = 0.6
    curiosity: float = 0.3
    excitement: float = 0.0
    confusion: float = 0.0

    def bump(self, event: str) -> None:
        de, dj, dc, dx, df = _EVENTS[event]
        self.energy = clamp(self.energy + de, 0, 1)
        self.joy = clamp(self.joy + dj, 0, 1)
        self.curiosity = clamp(self.curiosity + dc, 0, 1)
        self.excitement = clamp(self.excitement + dx, 0, 1)
        self.confusion = clamp(self.confusion + df, 0, 1)

    def update(self, dt: float, asleep: bool = False, moving: bool = False) -> None:
        if asleep:
            self.energy = clamp(self.energy + dt / 90.0, 0, 1)       # full recharge ~1.5 min
        else:
            self.energy = clamp(self.energy - dt / (420.0 if moving else 900.0), 0, 1)
            self.curiosity = clamp(self.curiosity + dt / 110.0, 0, 1)
        self.excitement = clamp(self.excitement - dt / 25.0, 0, 1)
        self.confusion = clamp(self.confusion - dt / 12.0, 0, 1)
        self.joy += (0.6 - self.joy) * min(1.0, dt / 300.0)

    @property
    def current(self) -> Mood:
        if self.confusion > 0.5:
            return Mood.CONFUSED
        if self.excitement > 0.5:
            return Mood.EXCITED
        if self.energy < 0.25:
            return Mood.SLEEPY
        if self.curiosity > 0.65:
            return Mood.CURIOUS
        return Mood.HAPPY
