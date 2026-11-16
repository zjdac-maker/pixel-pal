"""Pomodoro sessions, countdowns and reminders."""
from __future__ import annotations

import time

from ..core.timers import TimerManager, format_remaining
from .base import Ability, MenuItem


class TimerAbility(Ability):
    name = "timers"

    def setup(self, ctx) -> None:
        super().setup(ctx)
        self.manager = TimerManager()
        self.manager.load(ctx.config.timers)

    @property
    def focus_active(self) -> bool:
        return any(t.kind == "pomodoro" for t in self.manager.timers)

    def _persist(self) -> None:
        self.ctx.config.timers = self.manager.dump()
        self.ctx.save()

    def menu(self) -> list[MenuItem]:
        cfg, now = self.ctx.config, time.time()
        items = [
            MenuItem(f"Pomodoro ({cfg.pomodoro_minutes} min)", self.start_pomodoro),
            MenuItem(f"Break ({cfg.break_minutes} min)", self.start_break),
            MenuItem("Countdown…", self.ask_countdown),
            MenuItem("Reminder…", self.ask_reminder),
        ]
        if self.manager.timers:
            items.append(MenuItem("", separator=True))
            for t in sorted(self.manager.timers, key=lambda t: t.due):
                name = t.label or t.kind.capitalize()
                items.append(MenuItem(f"✕ {name}: {format_remaining(t.remaining(now))}",
                                      lambda t=t: self.cancel(t.id)))
            items.append(MenuItem("Cancel all", self.cancel_all))
        return [MenuItem("Timers", children=items)]

    def start_pomodoro(self) -> None:
        m = self.ctx.config.pomodoro_minutes
        self.manager.start("pomodoro", m * 60, "Focus")
        self._persist()
        self.ctx.say(f"Focus time! {m} minutes. I'll keep quiet.", 3.5)

    def start_break(self) -> None:
        m = self.ctx.config.break_minutes
        self.manager.start("break", m * 60, "Break")
        self._persist()
        self.ctx.say(f"Break time: {m} minutes.", 3)

    def ask_countdown(self) -> None:
        m = self.ctx.ask_number("Countdown", "Minutes:", 10, 1, 24 * 60)
        if m:
            self.manager.start("countdown", m * 60, f"{m} min timer")
            self._persist()
            self.ctx.say(f"{m} minutes on the clock!", 3)

    def ask_reminder(self) -> None:
        text = self.ctx.ask_text("Reminder", "Remind me to:")
        if not text or not text.strip():
            return
        m = self.ctx.ask_number("Reminder", "In how many minutes?", 30, 1, 7 * 24 * 60)
        if m:
            self.manager.start("reminder", m * 60, text.strip()[:80])
            self._persist()
            self.ctx.say(f"Got it. I'll remind you in {m} min.", 3)

    def cancel(self, timer_id: int) -> None:
        if self.manager.cancel(timer_id):
            self._persist()
            self.ctx.say("Timer cancelled.", 2)

    def cancel_all(self) -> None:
        if self.manager.cancel_all():
            self._persist()
            self.ctx.say("All timers cleared.", 2)

    def tick(self, now: float) -> None:
        fired = self.manager.poll()
        if not fired:
            return
        for t in fired:
            if t.kind == "pomodoro":
                self.ctx.celebrate("Focus session done. Stretch time!")
                if self.ctx.config.auto_break:
                    self.manager.start("break", self.ctx.config.break_minutes * 60, "Break")
            elif t.kind == "break":
                self.ctx.alert("Break's over. Ready when you are!")
            elif t.kind == "reminder":
                self.ctx.alert(f"Reminder: {t.label}")
            else:
                self.ctx.celebrate(f"Ding! {t.label or 'Timer'} is done!")
        self._persist()
