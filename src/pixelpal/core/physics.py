"""Gravity, collision and surface-following for the pet's body.

The body is a point at the centre of the pet's feet (``x``, ``y``) with a half width and
a height. ``step`` advances it and returns a list of events for the behaviour layer.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .geometry import clamp
from .world import Floor, Wall, World

GRAVITY = 1700.0        # px / s^2 at size factor 1
TERMINAL = 1500.0
ADJ_TOL = 2.0


class Mode(Enum):
    GROUND = "ground"
    AIR = "air"
    WALL = "wall"
    DRAGGED = "dragged"


@dataclass(frozen=True)
class Event:
    kind: str                 # landed | hit_wall | edge | fell_off | lost_surface | wall_top | wall_bottom | respawn
    wall: Wall | None = None
    speed: float = 0.0


@dataclass
class Body:
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    half_w: float = 24.0
    height: float = 48.0
    factor: float = 1.0        # scales gravity with sprite size
    mode: Mode = Mode.AIR
    floor: Floor | None = None
    wall: Wall | None = None
    facing: int = 1
    avoid_edges: bool = True   # stop at the end of a surface instead of walking off
    _ride: float = 0.0         # offset from the owning window's left/top edge

    # -- state changes used by the behaviour layer ------------------------------------
    def attach_floor(self, floor: Floor, world: World) -> None:
        self.mode, self.floor, self.wall = Mode.GROUND, floor, None
        self.y, self.vy = floor.y, 0.0
        self._remember(world)

    def attach_wall(self, wall: Wall, world: World) -> None:
        self.mode, self.wall, self.floor = Mode.WALL, wall, None
        self.x = wall.x + wall.side * self.half_w
        self.vx = self.vy = 0.0
        self.facing = -wall.side
        self.y = clamp(self.y, wall.y1 + self.height, wall.y2)
        self._remember(world)

    def launch(self, vx: float, vy: float) -> None:
        self.mode, self.floor, self.wall = Mode.AIR, None, None
        self.vx, self.vy = vx, vy
        if vx:
            self.facing = 1 if vx > 0 else -1

    def _remember(self, world: World) -> None:
        owner = self.floor.owner if self.floor else self.wall.owner if self.wall else None
        rect = world.window_rect(owner) if owner is not None else None
        if rect is None:
            return
        self._ride = self.x - rect.left if self.mode is Mode.GROUND else self.y - rect.top


def step(body: Body, world: World, dt: float) -> list[Event]:
    if body.mode is Mode.DRAGGED or not world.screens:
        return []
    events: list[Event] = []
    if body.mode is Mode.GROUND:
        _step_ground(body, world, dt, events)
    elif body.mode is Mode.WALL:
        _step_wall(body, world, dt, events)
    else:
        _step_air(body, world, dt, events)
    _keep_in_world(body, world, events)
    return events


# -- ground -----------------------------------------------------------------------------
def _step_ground(body: Body, world: World, dt: float, events: list[Event]) -> None:
    old = body.floor
    assert old is not None
    y = old.y
    if old.owner is not None:
        rect = world.window_rect(old.owner)
        if rect is None:
            return _lose(body, events)
        body.x, y = rect.left + body._ride, rect.top   # ride along with a moving window
    floor = world.floor_at(body.x, y, old.owner)
    if floor is None:
        return _lose(body, events)
    body.floor, body.y, body.vy = floor, floor.y, 0.0

    nx = body.x + body.vx * dt
    if body.vx:
        body.facing = 1 if body.vx > 0 else -1
    if not floor.contains_x(nx):
        end = floor.x1 if nx < floor.x1 else floor.x2
        direction = -1 if nx < floor.x1 else 1
        nxt = _adjacent_floor(world, floor, end, direction)
        wall = _wall_ahead(world, body, end, direction)
        if nxt is not None:
            body.floor = nxt
        elif wall is not None:
            nx = wall.x + wall.side * body.half_w
            events.append(Event("hit_wall", wall))
        elif body.avoid_edges:
            nx = end
            events.append(Event("edge"))
        else:
            body.x = nx
            body.launch(body.vx, 0.0)
            events.append(Event("fell_off"))
            return
    else:
        # A wall in the middle of a floor (side of a window standing on the taskbar line).
        wall = _wall_crossed(world, body, body.x, nx, body.y)
        if wall is not None:
            nx = wall.x + wall.side * body.half_w
            events.append(Event("hit_wall", wall))
    body.x = nx
    body._remember(world)


def _adjacent_floor(world: World, floor: Floor, end: float, direction: int) -> Floor | None:
    for f in world.floors:
        if f is floor or abs(f.y - floor.y) > ADJ_TOL:
            continue
        if direction > 0 and abs(f.x1 - end) <= ADJ_TOL or direction < 0 and abs(f.x2 - end) <= ADJ_TOL:
            return f
    return None


def _wall_ahead(world: World, body: Body, end: float, direction: int) -> Wall | None:
    for w in world.walls:
        if w.side == -direction and abs(w.x - end) <= ADJ_TOL and w.y1 < body.y and w.y2 >= body.y - ADJ_TOL:
            return w
    return None


def _wall_crossed(world: World, body: Body, x0: float, x1: float, y: float) -> Wall | None:
    """Wall whose line the body's leading edge passes when moving from x0 to x1."""
    if x1 == x0:
        return None
    direction = 1 if x1 > x0 else -1
    lead0, lead1 = x0 + direction * body.half_w, x1 + direction * body.half_w
    for w in world.walls:
        if w.side != -direction or not (w.y1 < y - 1 and w.y2 >= y - body.height / 2):
            continue
        if (lead0 - w.x) * direction <= 0 < (lead1 - w.x) * direction:
            return w
    return None


# -- air --------------------------------------------------------------------------------
def _step_air(body: Body, world: World, dt: float, events: list[Event]) -> None:
    body.vy = min(body.vy + GRAVITY * body.factor * dt, TERMINAL * body.factor)
    x0, y0 = body.x, body.y
    nx, ny = x0 + body.vx * dt, y0 + body.vy * dt

    wall = _wall_crossed(world, body, x0, nx, (y0 + ny) / 2)
    if wall is not None:
        if wall.owner is None:   # screen edges are solid; window sides are only grab-able
            nx = wall.x + wall.side * body.half_w
        events.append(Event("hit_wall", wall, abs(body.vx)))

    screen = world.nearest_screen(nx, ny - body.height / 2)
    if screen and body.vy < 0 and ny - body.height < screen.geometry.top:
        ny, body.vy = screen.geometry.top + body.height, 0.0

    if body.vy >= 0:
        landing = None
        for f in world.floors:
            if f.contains_x(nx) and y0 - 0.5 <= f.y <= ny and (landing is None or f.y < landing.y):
                landing = f
        if landing is not None:
            speed = body.vy
            body.x = nx
            body.attach_floor(landing, world)
            body.vx = 0.0
            events.append(Event("landed", speed=speed))
            return
    body.x, body.y = nx, ny


# -- wall -------------------------------------------------------------------------------
def _step_wall(body: Body, world: World, dt: float, events: list[Event]) -> None:
    old = body.wall
    assert old is not None
    x = old.x
    if old.owner is not None:
        rect = world.window_rect(old.owner)
        if rect is None:
            return _lose(body, events)
        x = rect.left if old.side < 0 else rect.right
        body.y = rect.top + body._ride
    mid = body.y - body.height / 2
    wall = world.wall_at(x, mid, old.side, old.owner)
    if wall is None:
        return _lose(body, events)
    body.wall, body.x, body.vx = wall, wall.x + wall.side * body.half_w, 0.0

    ny = body.y + body.vy * dt
    if ny - body.height <= wall.y1 and body.vy < 0:
        ny = wall.y1 + body.height
        events.append(Event("wall_top", wall))
    elif ny >= wall.y2 and body.vy > 0:
        ny = wall.y2
        floor = world.floor_below(body.x, ny - 1)
        if floor is not None and floor.y - ny <= ADJ_TOL:
            body.y = ny
            body.attach_floor(floor, world)
            events.append(Event("landed", speed=0.0))
            return
        events.append(Event("wall_bottom", wall))
    body.y = ny
    body._remember(world)


# -- shared -----------------------------------------------------------------------------
def _lose(body: Body, events: list[Event]) -> None:
    body.launch(0.0, 0.0)
    events.append(Event("lost_surface"))


def _keep_in_world(body: Body, world: World, events: list[Event]) -> None:
    """Never let the pet end up somewhere the user cannot see it."""
    screen = world.screen_at(body.x, body.y - body.height / 2)
    if screen is not None:
        if body.mode is Mode.AIR and body.y > screen.work.bottom:
            floor = world.floor_at(body.x, screen.work.bottom, None)
            if floor is not None:
                body.attach_floor(floor, world)
                body.vx = 0.0
                events.append(Event("landed", speed=0.0))
        return
    near = world.nearest_screen(body.x, body.y)
    assert near is not None
    g = near.geometry
    if body.mode is Mode.AIR and g.left - 4 * body.half_w <= body.x <= g.right + 4 * body.half_w \
            and body.y <= g.bottom + body.height:
        # Just past an edge (dragged or thrown there): nudge back in rather than teleport.
        body.x = clamp(body.x, near.work.left + body.half_w, near.work.right - body.half_w)
        return
    respawn(body, world)
    events.append(Event("respawn"))


def respawn(body: Body, world: World, x: float | None = None, screen=None) -> None:
    """Drop the pet in from the top of a screen."""
    s = screen or (world.nearest_screen(x, 0) if x is not None else None) or world.screens[0]
    body.x = clamp(x if x is not None else s.work.center_x, s.work.left + body.half_w, s.work.right - body.half_w)
    body.y = s.work.top + body.height
    body.launch(0.0, 0.0)


def plan_jump(body: Body, tx: float, ty: float, clearance: float = 30.0,
              max_rise: float = 520.0, max_vx: float = 520.0) -> tuple[float, float] | None:
    """Launch velocity that lands the body on (tx, ty), or None if it is out of reach."""
    g = GRAVITY * body.factor
    apex = min(body.y, ty) - clearance * body.factor
    rise = body.y - apex
    if rise > max_rise * body.factor:
        return None
    vy = -math.sqrt(2 * g * rise)
    t = -vy / g + math.sqrt(2 * (ty - apex) / g)
    vx = (tx - body.x) / t
    if abs(vx) > max_vx * body.factor:
        return None
    return vx, vy
