"""The pet's view of the desktop: screens and windows turned into floors and walls.

Everything is in Qt logical (device-independent) pixels with y growing downwards.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import Rect, subtract_intervals


@dataclass(frozen=True)
class ScreenInfo:
    geometry: Rect  # full monitor
    work: Rect      # monitor minus taskbar


@dataclass(frozen=True)
class WindowInfo:
    """A top-level application window. Lists of these are ordered top-most first."""
    id: int
    rect: Rect
    title: str = ""


@dataclass(frozen=True)
class Floor:
    """Horizontal segment the pet can stand on. ``owner`` is a window id or None for a screen."""
    y: float
    x1: float
    x2: float
    owner: int | None = None

    def contains_x(self, x: float) -> bool:
        return self.x1 <= x <= self.x2


@dataclass(frozen=True)
class Wall:
    """Vertical segment the pet can climb.

    ``side`` says where the pet is relative to the line: +1 = pet is to the right of it
    (left screen edge, right side of a window), -1 = pet is to the left of it.
    """
    x: float
    y1: float
    y2: float
    side: int
    owner: int | None = None

    def contains_y(self, y: float) -> bool:
        return self.y1 <= y <= self.y2


MIN_FLOOR = 24.0      # shortest window-top segment worth standing on
MIN_WALL = 40.0       # shortest wall segment worth climbing
HEADROOM = 40.0       # a window top needs this much free screen above it
EDGE_TOL = 2.0


@dataclass
class World:
    screens: list[ScreenInfo] = field(default_factory=list)
    windows: list[WindowInfo] = field(default_factory=list)
    floors: list[Floor] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)

    # -- construction -----------------------------------------------------------------
    @classmethod
    def build(cls, screens: list[ScreenInfo], windows: list[WindowInfo] | None = None) -> "World":
        world = cls(screens=list(screens), windows=list(windows or []))
        world._build_screen_surfaces()
        world._build_window_surfaces()
        return world

    def _build_screen_surfaces(self) -> None:
        for s in self.screens:
            w = s.work
            self.floors.append(Floor(w.bottom, w.left, w.right, None))
            for x, side in ((w.left, 1), (w.right, -1)):
                # An edge shared with a neighbouring monitor is not a wall there.
                cuts = [(o.work.top, o.work.bottom) for o in self.screens if o is not s
                        and (abs(o.work.right - x) <= EDGE_TOL if side == 1 else abs(o.work.left - x) <= EDGE_TOL)]
                for y1, y2 in subtract_intervals((w.top, w.bottom), cuts, MIN_WALL):
                    self.walls.append(Wall(x, y1, y2, side, None))

    def _build_window_surfaces(self) -> None:
        for i, win in enumerate(self.windows):
            r = win.rect
            above = [w.rect for w in self.windows[:i]]  # windows that can hide this one
            for s in self.screens:
                wk = s.work
                # Top edge -> floor, clipped to the screen and to what is not hidden.
                if wk.top + HEADROOM <= r.top < wk.bottom - EDGE_TOL:
                    x1, x2 = max(r.left, wk.left), min(r.right, wk.right)
                    if x2 - x1 > MIN_FLOOR:
                        cuts = [(a.left, a.right) for a in above if a.top < r.top < a.bottom]
                        for a, b in subtract_intervals((x1, x2), cuts, MIN_FLOOR):
                            self.floors.append(Floor(r.top, a, b, win.id))
                # Left and right edges -> walls on the outside of the window.
                y1, y2 = max(r.top, wk.top), min(r.bottom, wk.bottom)
                if y2 - y1 <= MIN_WALL:
                    continue
                for x, side in ((r.left, -1), (r.right, 1)):
                    if not (wk.left + EDGE_TOL < x < wk.right - EDGE_TOL):
                        continue
                    cuts = [(a.top, a.bottom) for a in above if a.left < x < a.right]
                    for a, b in subtract_intervals((y1, y2), cuts, MIN_WALL):
                        self.walls.append(Wall(x, a, b, side, win.id))

    # -- queries ----------------------------------------------------------------------
    def window_rect(self, owner: int) -> Rect | None:
        for w in self.windows:
            if w.id == owner:
                return w.rect
        return None

    def screen_at(self, x: float, y: float) -> ScreenInfo | None:
        for s in self.screens:
            if s.geometry.contains(x, y):
                return s
        return None

    def nearest_screen(self, x: float, y: float) -> ScreenInfo | None:
        if not self.screens:
            return None
        hit = self.screen_at(x, y)
        if hit:
            return hit
        return min(self.screens, key=lambda s: (s.geometry.center_x - x) ** 2 + (s.geometry.center_y - y) ** 2)

    def floor_at(self, x: float, y: float, owner: int | None, tol: float = 1.5) -> Floor | None:
        for f in self.floors:
            if f.owner == owner and abs(f.y - y) <= tol and f.contains_x(x):
                return f
        return None

    def wall_at(self, x: float, y: float, side: int, owner: int | None, tol: float = 1.5) -> Wall | None:
        for w in self.walls:
            if w.owner == owner and w.side == side and abs(w.x - x) <= tol and w.contains_y(y):
                return w
        return None

    def floor_below(self, x: float, y: float) -> Floor | None:
        """Highest floor at or below ``y`` in the column ``x``."""
        best = None
        for f in self.floors:
            if f.contains_x(x) and f.y >= y - 0.5 and (best is None or f.y < best.y):
                best = f
        return best

    def fullscreen_on(self, x: float, y: float) -> bool:
        """True if the top-most window fills the whole monitor under (x, y) (video, game...)."""
        s = self.screen_at(x, y)
        if not s:
            return False
        for w in self.windows:
            if w.rect.covers(s.geometry, slack=1.0):
                return True
            if w.rect.contains(x, y):
                return False  # something not fullscreen is on top here
        return False
