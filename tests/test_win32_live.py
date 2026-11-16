"""Runs only on Windows (for example in CI): exercises the real Win32 calls."""
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows only")


def test_real_window_enumeration_and_system_sample():
    from pixelpal.platform.base import get_platform
    platform = get_platform()
    assert platform.name == "windows"
    windows = platform.list_windows()                 # may be empty on a headless runner
    assert all(w.rect.width >= 120 and w.title for w in windows)
    platform.sample_system()
    sample = platform.sample_system()                 # the second call has a CPU delta
    assert sample.cpu_percent is None or 0 <= sample.cpu_percent <= 100
    assert sample.battery_percent is None or 0 <= sample.battery_percent <= 100


def test_autostart_toggle_round_trip():
    from pixelpal.platform.base import get_platform
    platform = get_platform()
    before = platform.autostart_enabled()
    try:
        platform.set_autostart(True)
        assert platform.autostart_enabled()
        platform.set_autostart(False)
        assert not platform.autostart_enabled()
    finally:
        platform.set_autostart(before)
