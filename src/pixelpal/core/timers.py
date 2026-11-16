"""Countdowns, Pomodoro sessions and reminders. Pure logic with an injectable clock."""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Callable

KINDS = ("countdown", "pomodoro", "break", "reminder")


@dataclass
class Timer:
    id: int
    kind: str
    label: str
    due: float          # epoch seconds

    def remaining(self, now: float) -> float:
        return max(0.0, self.due - now)


class TimerManager:
    def __init__(self, clock: Callable[[], float] = time.time) -> None:
        self.clock = clock
        self.timers: list[Timer] = []
        self._next_id = 1

    def start(self, kind: str, seconds: float, label: str = "") -> Timer:
        if kind not in KINDS:
            raise ValueError(f"unknown timer kind: {kind}")
        if seconds <= 0:
            raise ValueError("a timer needs a positive duration")
        t = Timer(self._next_id, kind, label, self.clock() + seconds)
        self._next_id += 1
        self.timers.append(t)
        return t

    def cancel(self, timer_id: int) -> bool:
        before = len(self.timers)
        self.timers = [t for t in self.timers if t.id != timer_id]
        return len(self.timers) != before

    def cancel_all(self) -> int:
        n = len(self.timers)
        self.timers = []
        return n

    def poll(self) -> list[Timer]:
        """Remove and return every timer that is due."""
        now = self.clock()
        due = sorted((t for t in self.timers if t.due <= now), key=lambda t: t.due)
        self.timers = [t for t in self.timers if t.due > now]
        return due

    # persistence, so reminders survive a restart
    def dump(self) -> list[dict]:
        return [asdict(t) for t in self.timers]

    def load(self, items: list[dict]) -> None:
        for item in items:
            try:
                t = Timer(int(item["id"]), str(item["kind"]), str(item.get("label", "")), float(item["due"]))
            except (KeyError, TypeError, ValueError):
                continue
            if t.kind in KINDS:
                self.timers.append(t)
                self._next_id = max(self._next_id, t.id + 1)


def format_remaining(seconds: float) -> str:
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
