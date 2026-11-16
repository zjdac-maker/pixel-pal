"""Reacts to low battery and sustained high CPU."""
from __future__ import annotations

from ..core.sysmon import SystemWatcher
from .base import Ability

INTERVAL = 5.0


class SystemMonitorAbility(Ability):
    name = "system monitor"

    def setup(self, ctx) -> None:
        super().setup(ctx)
        self.watcher = SystemWatcher()
        self._next = 0.0

    def tick(self, now: float) -> None:
        cfg = self.ctx.config
        if not cfg.monitor_system or now < self._next:
            return
        self._next = now + INTERVAL
        self.watcher.battery_threshold = cfg.battery_threshold
        self.watcher.cpu_threshold = cfg.cpu_threshold
        for alert in self.watcher.feed(self.ctx.platform.sample_system(), now):
            if alert.kind == "low_battery":
                self.ctx.alert(f"Psst… battery's at {alert.value}%. Feed the laptop!")
            else:
                self.ctx.alert(f"Phew, it's warm in here. CPU at {alert.value}%!")
