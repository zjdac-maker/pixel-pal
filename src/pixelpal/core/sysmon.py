"""Turns raw battery / CPU samples into occasional, non-nagging alerts."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Sample:
    cpu_percent: float | None = None       # None = unknown
    battery_percent: int | None = None     # None = no battery / unknown
    on_ac: bool = True


@dataclass(frozen=True)
class Alert:
    kind: str      # low_battery | high_cpu
    value: int


class SystemWatcher:
    def __init__(self, battery_threshold: int = 20, cpu_threshold: int = 90,
                 cpu_sustain: int = 4, cpu_cooldown: float = 600.0) -> None:
        self.battery_threshold = battery_threshold
        self.cpu_threshold = cpu_threshold
        self.cpu_sustain = cpu_sustain          # consecutive hot samples before speaking up
        self.cpu_cooldown = cpu_cooldown
        self._battery_warned = False
        self._hot = 0
        self._cpu_quiet_until = 0.0

    def feed(self, sample: Sample, now: float) -> list[Alert]:
        alerts: list[Alert] = []
        b = sample.battery_percent
        if b is not None:
            if not sample.on_ac and b <= self.battery_threshold:
                if not self._battery_warned:
                    self._battery_warned = True
                    alerts.append(Alert("low_battery", b))
            elif sample.on_ac or b > self.battery_threshold + 5:
                self._battery_warned = False     # re-arm once charging or recovered
        c = sample.cpu_percent
        if c is not None:
            self._hot = self._hot + 1 if c >= self.cpu_threshold else 0
            if self._hot >= self.cpu_sustain and now >= self._cpu_quiet_until:
                self._cpu_quiet_until = now + self.cpu_cooldown
                self._hot = 0
                alerts.append(Alert("high_cpu", int(round(c))))
        return alerts
