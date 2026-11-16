"""Drives the real Qt application headlessly (offscreen platform) with fake windows."""
import gc
import random

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication, QEvent, QPoint
from PySide6.QtWidgets import QApplication

from pixelpal.app import PetController
from pixelpal.config import Automation, Config
from pixelpal.core.behavior import Action
from pixelpal.core.geometry import Rect
from pixelpal.core.physics import Mode
from pixelpal.platform.base import NativeWindow, Platform
from pixelpal.ui.settings import SettingsDialog


class FakeDesktop(Platform):
    supports_windows = True

    def __init__(self):
        self.windows = [NativeWindow(7, Rect(150, 350, 650, 700), "Editor")]

    def list_windows(self):
        return list(self.windows)


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app
    # Shut Qt down while Python is still fully alive. Leaving it to interpreter exit lets
    # widgets and the application die in random order, which can crash after the tests pass.
    for widget in app.topLevelWidgets():
        widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()
    app.shutdown()


@pytest.fixture
def pet(qapp):
    controller = PetController(Config(), FakeDesktop(), rng=random.Random(4))
    controller.start()
    controller.timer.stop()               # the test drives the clock itself
    yield controller
    # Tear everything down now, in a known order, instead of at interpreter exit.
    if controller.tray:
        controller.tray.hide()
    for obj in (controller.window, controller.bubble, controller):
        obj.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    qapp.processEvents()


def advance(pet, seconds, dt=1 / 30):
    for _ in range(int(seconds / dt)):
        pet._last -= dt                   # pretend dt has passed, then run a real frame
        pet.tick()


def test_pet_window_is_transparent_topmost_and_never_takes_focus(pet):
    from PySide6.QtCore import Qt
    flags = pet.window.windowFlags()
    for flag in (Qt.WindowType.FramelessWindowHint, Qt.WindowType.WindowStaysOnTopHint,
                 Qt.WindowType.Tool, Qt.WindowType.WindowDoesNotAcceptFocus):
        assert flags & flag
    assert pet.window.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert pet.bubble.windowFlags() & Qt.WindowType.WindowTransparentForInput
    assert pet.window.width() == 32 * pet.config.scale


def test_drawn_frame_has_transparent_surroundings_and_an_opaque_body(pet):
    advance(pet, 3)
    img = pet.window.grab().toImage()
    assert img.pixelColor(1, 1).alpha() == 0
    assert img.pixelColor(img.width() // 2, int(img.height() * 0.85)).alpha() == 255


def test_window_tracks_the_body_and_lands(pet):
    advance(pet, 4)
    assert pet.body.mode is Mode.GROUND
    assert pet.window.x() == round(pet.body.x - pet.window.width() / 2)
    assert pet.window.y() + 31 * pet.config.scale == round(pet.body.y)


def test_drag_throw_and_pet_via_window_signals(pet):
    advance(pet, 3)
    start = QPoint(round(pet.body.x), round(pet.body.y) - 20)
    pet.window.grabbed.emit(start)
    pet.window.dragged.emit(QPoint(400, 200))
    assert pet.body.mode is Mode.DRAGGED and round(pet.body.x) == 400
    advance(pet, 0.5)
    assert pet.brain.action is Action.DRAGGED and round(pet.body.x) == 400
    pet.window.released.emit(0.0, 0.0)
    advance(pet, 3)
    assert pet.body.mode is Mode.GROUND
    assert pet.body.floor.owner == 7 and pet.body.y == 350          # dropped onto the fake window
    pet.brain._set(Action.IDLE, 5)
    pet.window.petted.emit()
    assert pet.brain.action is Action.PETTED


def test_pet_falls_when_window_is_minimised_and_reacts_to_fullscreen(pet):
    advance(pet, 1)
    pet.window.grabbed.emit(QPoint(round(pet.body.x), round(pet.body.y)))
    pet.window.dragged.emit(QPoint(400, 200))
    pet.window.released.emit(0.0, 0.0)
    advance(pet, 3)
    assert pet.body.y == 350
    pet.platform.windows = []
    advance(pet, 3)
    assert pet.body.mode is Mode.GROUND and pet.body.y > 350
    pet.platform.windows = [NativeWindow(9, Rect(0, 0, 800, 800), "Video")]   # covers the whole test screen
    advance(pet, 1)
    assert not pet.window.isVisible()
    pet.platform.windows = []
    advance(pet, 1)
    assert pet.window.isVisible()


def test_speech_bubble_and_celebration_rewards(pet):
    advance(pet, 3)
    pet.celebrate("Timer done!")
    assert pet.bubble.isVisible() and "Timer done!" in pet.bubble.text and "bow" in pet.bubble.text
    assert pet.config.tasks_done == 1 and pet.config.accessory == "bow"
    assert pet.brain.action is Action.CELEBRATE
    pet.config.speech_bubbles = False
    pet.bubble.hide()
    pet.say("small talk")
    assert not pet.bubble.isVisible()
    pet.alert("Battery low")                  # important messages still show
    assert pet.bubble.isVisible()


def test_menu_lists_abilities_and_quiet_toggle(pet):
    labels = [i.label for i in pet.menu_items()]
    assert labels[:3] == ["Open", "Timers", "Automations"]
    assert {"Come here!", "Take a nap", "Quiet mode", "Settings…", "Quit pixel-pal"} <= set(labels)
    pet.show_menu(QPoint(10, 10))
    assert len(pet._menu.actions()) == len(labels)
    pet._menu.close()
    pet.toggle_quiet()
    assert pet.config.quiet_mode and pet.brain.settings.quiet


def test_settings_dialog_round_trip(pet):
    dialog = SettingsDialog(pet.config, pet.platform)
    dialog.scale.setValue(5)
    dialog.activity.setValue(20)
    dialog.colour = "#8ec9f5"
    dialog._add_automation(Automation("Backup", "robocopy a b"))
    dialog.apply()
    pet.apply_config()
    assert pet.config.scale == 5 and pet.config.activity == 0.2 and pet.config.body_colour == "#8ec9f5"
    assert pet.window.width() == 160 and pet.body.half_w == 40
    assert [a.name for a in pet.config.automations] == ["Backup"] and not pet.config.automations[0].approved
    assert len(pet.config.quick_actions) == 3


def test_ten_minutes_of_real_frames_stays_on_screen(pet):
    advance(pet, 600)
    screen = QApplication.primaryScreen().geometry()
    assert screen.left() <= pet.body.x <= screen.right()
    assert screen.top() <= pet.body.y <= screen.bottom() + 1
