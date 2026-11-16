import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from pixelpal.core.geometry import Rect
from pixelpal.core.world import ScreenInfo, WindowInfo, World


@pytest.fixture
def screen():
    return ScreenInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))


@pytest.fixture
def world(screen):
    return World.build([screen], [WindowInfo(1, Rect(400, 300, 1000, 700), "Editor")])


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    monkeypatch.setenv("PIXELPAL_HOME", str(tmp_path / "home"))
