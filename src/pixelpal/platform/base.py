"""Platform interface. The pet only ever talks to these, never to an OS API directly."""
from __future__ import annotations

from dataclasses import dataclass

from ..core.geometry import Rect
from ..core.sysmon import Sample


@dataclass(frozen=True)
class NativeWindow:
    """A window as the OS reports it, in *physical* pixels, top-most first in lists."""
    id: int
    rect: Rect
    title: str = ""


class Platform:
    """Safe fallback used on anything that is not Windows: screen edges only."""

    name = "generic"
    supports_windows = False
    supports_autostart = False

    def list_windows(self) -> list[NativeWindow]:
        return []

    def sample_system(self) -> Sample:
        return Sample()

    def open_path(self, target: str) -> None:
        import subprocess
        import sys
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", target])

    def autostart_enabled(self) -> bool:
        return False

    def set_autostart(self, enabled: bool) -> None:
        raise NotImplementedError("Launch at login is only available on Windows")


@dataclass(frozen=True)
class ScreenScale:
    """One monitor: its Qt logical geometry and device pixel ratio."""
    logical: Rect
    dpr: float

    @property
    def native(self) -> Rect:
        # Qt keeps a screen's origin at its physical position and scales only its size.
        g = self.logical
        return Rect(g.left, g.top, g.left + g.width * self.dpr, g.top + g.height * self.dpr)


def native_to_logical(rect: Rect, screens: list[ScreenScale]) -> Rect:
    """Convert a physical-pixel window rectangle to Qt logical pixels.

    The window is attributed to the monitor containing its centre (nearest one otherwise).
    """
    if not screens:
        return rect
    cx, cy = rect.center_x, rect.center_y

    def distance(s: ScreenScale) -> float:
        n = s.native
        dx = max(n.left - cx, 0, cx - n.right)
        dy = max(n.top - cy, 0, cy - n.bottom)
        return dx * dx + dy * dy

    s = min(screens, key=distance)
    ox, oy, d = s.logical.left, s.logical.top, s.dpr
    return Rect(ox + (rect.left - ox) / d, oy + (rect.top - oy) / d,
                ox + (rect.right - ox) / d, oy + (rect.bottom - oy) / d)


def get_platform() -> Platform:
    import sys
    if sys.platform == "win32":
        try:
            from .win32 import WindowsPlatform
            return WindowsPlatform()
        except Exception:       # never let an API surprise stop the pet from starting
            pass
    return Platform()
