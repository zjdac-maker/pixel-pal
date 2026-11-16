"""The controller: wires the brain, physics, sprites, windows and abilities together."""
from __future__ import annotations

import random
import time
from typing import Callable

from PySide6.QtCore import QObject, QPoint, QRect, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtWidgets import QApplication, QInputDialog, QMessageBox, QSystemTrayIcon

from .abilities import Ability, MenuItem, default_abilities
from .config import Config
from .core import physics
from .core.animation import Animator
from .core.behavior import RESTING, Action, Brain, BrainSettings
from .core.geometry import Rect
from .core.mood import MoodState
from .core.personality import Chatter, newly_unlocked, phrase
from .core.physics import Body, Mode
from .core.world import ScreenInfo, WindowInfo, World
from .platform.base import Platform, ScreenScale, get_platform, native_to_logical
from .sprites import pip
from .ui.bubble import SpeechBubble
from .ui.menu import build_menu
from .ui.pet_window import PetWindow
from .ui.render import SpriteRenderer
from .ui.settings import SettingsDialog

ACTIVE_MS, RESTING_MS = 33, 120       # ~30 fps while moving, ~8 fps while resting
WORLD_REFRESH = 0.25                  # seconds between window scans
MAX_DT = 0.05


def _rect(r: QRect) -> Rect:
    return Rect(r.x(), r.y(), r.x() + r.width(), r.y() + r.height())


class PetController(QObject):
    _invoke = Signal(object)

    def __init__(self, config: Config | None = None, platform: Platform | None = None,
                 abilities: list[Ability] | None = None, rng: random.Random | None = None) -> None:
        super().__init__()
        self.config = config or Config.load()
        self.platform = platform or get_platform()
        self.rng = rng or random.Random()
        self.renderer = SpriteRenderer(self.config.body_colour, self.config.scale)
        self.window = PetWindow()
        self.bubble = SpeechBubble()
        self.body = Body()
        self.mood = MoodState()
        self.brain = Brain(self.body, self.mood, BrainSettings(), self.rng)
        self.animator = Animator(pip.ANIMATIONS)
        self.chatter = Chatter(self.rng)
        self.world = World()
        self.tray: QSystemTrayIcon | None = None
        self._menu = None
        self._grab_offset = (0.0, 0.0)
        self._last = time.monotonic()
        self._world_age = 99.0
        self._ability_age = 0.0
        self._hidden_for_fullscreen = False
        self._invoke.connect(lambda fn: fn())      # queued when emitted from a worker thread

        self.window.grabbed.connect(self._on_grab)
        self.window.dragged.connect(self._on_drag)
        self.window.released.connect(self._on_release)
        self.window.petted.connect(self._on_pet)
        self.window.menu_requested.connect(self.show_menu)
        app = QGuiApplication.instance()
        app.screenAdded.connect(lambda *_: self._refresh_world(force=True))
        app.screenRemoved.connect(lambda *_: self._refresh_world(force=True))

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.abilities = abilities if abilities is not None else default_abilities()
        self.apply_config()
        for ability in self.abilities:
            ability.setup(self)

    # -- lifecycle ----------------------------------------------------------------------------
    def start(self) -> None:
        self._refresh_world(force=True)
        screen = QGuiApplication.primaryScreen().availableGeometry()
        physics.respawn(self.body, self.world, screen.x() + screen.width() * self.rng.uniform(0.3, 0.7))
        self._setup_tray()
        self._sync_window()
        self.window.show()
        self._last = time.monotonic()
        self.timer.start(ACTIVE_MS)
        QTimer.singleShot(1500, lambda: self.say(phrase("hello", self.rng), 3.5))

    def quit(self) -> None:
        self.timer.stop()
        for ability in self.abilities:
            ability.shutdown()
        self.save()
        if self.tray:
            self.tray.hide()
        QApplication.instance().quit()

    def apply_config(self) -> None:
        c = self.config
        self.renderer.configure(c.body_colour, c.scale)
        self.body.factor = c.scale / 3.0
        self.body.half_w = pip.BODY_RX * c.scale
        self.body.height = pip.BODY_H * c.scale
        size = self.renderer.logical_size
        self.window.setFixedSize(size, size)
        s = self.brain.settings
        s.activity, s.follow_cursor, s.climbing, s.quiet = c.activity, c.follow_cursor, c.climbing, c.quiet_mode
        if self.tray:
            self.tray.setIcon(self.renderer.icon())
        self._world_age = 99.0

    def save(self) -> None:
        try:
            self.config.save()
        except OSError:
            pass    # a read-only profile must not crash the pet

    # -- the frame ----------------------------------------------------------------------------
    def tick(self) -> None:
        now = time.monotonic()
        dt = min(MAX_DT * 4, now - self._last)
        self._last = now

        self._world_age += dt
        if self._world_age >= WORLD_REFRESH:
            self._refresh_world()

        cursor = QCursor.pos()
        steps = max(1, round(dt / MAX_DT + 0.49))       # keep physics stable at the slow tick rate
        for _ in range(steps):
            self.brain.update(dt / steps, self.world, (cursor.x(), cursor.y()))
            events = physics.step(self.body, self.world, dt / steps)
            if events:
                self.brain.handle(events, self.world)
                self._react(events)

        action = self.brain.action
        self.animator.play("run" if action is Action.FOLLOW else action.value)
        self.animator.update(dt)
        self._sync_window()

        line = self.chatter.update(dt, self.mood.current, self.config.chattiness,
                                   self.config.quiet_mode or self._focus_active(), self.brain.asleep)
        if line:
            self.say(line, 3.5)

        self._ability_age += dt
        if self._ability_age >= 1.0:
            self._ability_age = 0.0
            wall_clock = time.time()
            for ability in self.abilities:
                ability.tick(wall_clock)

        resting = action in RESTING and self.body.mode is not Mode.AIR and not self.bubble.isVisible()
        interval = RESTING_MS if resting else ACTIVE_MS
        if self.timer.interval() != interval:
            self.timer.setInterval(interval)

    def _react(self, events: list[physics.Event]) -> None:
        for ev in events:
            if ev.kind == "landed" and self.brain.action is Action.DIZZY:
                self.say(phrase("thrown", self.rng), 2.5)
            elif ev.kind == "lost_surface" and self.rng.random() < 0.5:
                self.say(phrase("lost_surface", self.rng), 2.5)

    def _focus_active(self) -> bool:
        return any(getattr(a, "focus_active", False) for a in self.abilities)

    def _refresh_world(self, force: bool = False) -> None:
        self._world_age = 0.0
        qscreens = QGuiApplication.screens()
        screens = [ScreenInfo(_rect(s.geometry()), _rect(s.availableGeometry())) for s in qscreens]
        windows: list[WindowInfo] = []
        if self.config.window_interaction and self.platform.supports_windows:
            scales = [ScreenScale(_rect(s.geometry()), s.devicePixelRatio()) for s in qscreens]
            windows = [WindowInfo(w.id, native_to_logical(w.rect, scales), w.title)
                       for w in self.platform.list_windows()]
        if force or screens != self.world.screens or windows != self.world.windows:
            self.world = World.build(screens, windows)
        if self.config.hide_in_fullscreen:
            hide = self.world.fullscreen_on(self.body.x, self.body.y - self.body.height / 2)
            if hide != self._hidden_for_fullscreen:
                self._hidden_for_fullscreen = hide
                self.window.setVisible(not hide)
                if hide:
                    self.bubble.hide()

    def _sync_window(self) -> None:
        scale = self.config.scale
        x = round(self.body.x - self.window.width() / 2)
        y = round(self.body.y - (pip.BASE + 1) * scale)
        if self.window.x() != x or self.window.y() != y:
            self.window.move(x, y)
        self.window.set_pixmap(self.renderer.pixmap(
            self.animator.frame, self.config.accessory, self.body.facing, self.window.devicePixelRatioF()))
        if self.bubble.isVisible():
            self._place_bubble()

    def _place_bubble(self) -> None:
        screen = QGuiApplication.screenAt(QPoint(round(self.body.x), round(self.body.y - 4))) \
            or QGuiApplication.primaryScreen()
        head_y = round(self.body.y - (pip.BODY_H + 7) * self.config.scale)
        self.bubble.place(round(self.body.x), head_y, screen.availableGeometry())

    # -- mouse --------------------------------------------------------------------------------
    def _on_grab(self, pos: QPoint) -> None:
        self._grab_offset = (self.body.x - pos.x(), self.body.y - pos.y())
        self.brain.grab()

    def _on_drag(self, pos: QPoint) -> None:
        self.body.x, self.body.y = pos.x() + self._grab_offset[0], pos.y() + self._grab_offset[1]
        self._sync_window()

    def _on_release(self, vx: float, vy: float) -> None:
        self.brain.release(vx, vy)

    def _on_pet(self) -> None:
        was_asleep = self.brain.asleep
        self.brain.pet()
        if self.rng.random() < 0.6 or was_asleep:
            self.say(phrase("woke" if was_asleep else "petted", self.rng), 2.0)

    # -- AbilityContext -----------------------------------------------------------------------
    def say(self, text: str, seconds: float = 4.0, important: bool = False) -> None:
        if not text or self._hidden_for_fullscreen:
            return
        if not important and (not self.config.speech_bubbles):
            return
        self.bubble.say(text, seconds)
        self._place_bubble()
        self.bubble.show()

    def celebrate(self, text: str = "") -> None:
        self.brain.wake()
        self.brain.celebrate()
        before = self.config.tasks_done
        self.config.tasks_done += 1
        earned = newly_unlocked(before, self.config.tasks_done)
        if earned:
            self.config.accessory = earned[-1].accessory
            text = f"{text} {phrase('unlock', self.rng, earned[-1].label)}".strip()
        self.save()
        self.say(text or phrase("task_done", self.rng), 5.0, important=True)

    def alert(self, text: str) -> None:
        self.brain.wake()
        self.brain.alert()
        self.say(text, 7.0, important=True)

    def confuse(self, text: str = "") -> None:
        self.brain.wake()
        self.brain.confuse()
        self.say(text or phrase("task_failed", self.rng), 5.0, important=True)

    def ask_number(self, title: str, label: str, default: int, lo: int, hi: int) -> int | None:
        value, ok = QInputDialog.getInt(None, title, label, default, lo, hi)
        return value if ok else None

    def ask_text(self, title: str, label: str, default: str = "") -> str | None:
        value, ok = QInputDialog.getText(None, title, label, text=default)
        return value if ok else None

    def confirm(self, title: str, text: str) -> bool:
        box = QMessageBox(QMessageBox.Icon.Question, title, text,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        return box.exec() == QMessageBox.StandardButton.Yes

    def run_later(self, fn: Callable[[], None]) -> None:
        self._invoke.emit(fn)

    # -- menu, tray, settings -----------------------------------------------------------------
    def menu_items(self) -> list[MenuItem]:
        items: list[MenuItem] = []
        for ability in self.abilities:
            items.extend(ability.menu())
        items += [
            MenuItem("", separator=True),
            MenuItem("Come here!", self.summon),
            MenuItem("Wake up" if self.brain.asleep else "Take a nap",
                     self.brain.wake if self.brain.asleep else self.brain.sleep),
            MenuItem("Quiet mode", self.toggle_quiet, checked=self.config.quiet_mode),
            MenuItem("", separator=True),
            MenuItem("Settings…", self.open_settings),
            MenuItem("Quit pixel-pal", self.quit),
        ]
        return items

    def show_menu(self, pos: QPoint) -> None:
        self._menu = build_menu(self.menu_items())
        self._menu.popup(pos)

    def summon(self) -> None:
        self._hidden_for_fullscreen = False
        self.window.show()
        self.brain.summon(self.world, QCursor.pos().x())

    def toggle_quiet(self) -> None:
        self.config.quiet_mode = not self.config.quiet_mode
        self.apply_config()
        self.save()
        self.say("Shh. Quiet mode." if self.config.quiet_mode else "I'm back!", 2.5, important=True)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.config, self.platform)
        if dialog.exec():
            dialog.apply()
            self.apply_config()
            self.save()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(self.renderer.icon(), self)
        self.tray.setToolTip("pixel-pal")
        menu = build_menu([])
        menu.aboutToShow.connect(lambda: self._rebuild(menu))
        self._tray_menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(
            lambda reason: self.summon() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.tray.show()

    def _rebuild(self, menu) -> None:
        from .ui.menu import _fill
        menu.clear()
        _fill(menu, self.menu_items())
