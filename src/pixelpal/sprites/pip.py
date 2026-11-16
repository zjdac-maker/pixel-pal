"""Pip, the original pixel-pal character: a round sprout creature drawn procedurally.

Every frame is a 32x32 grid of palette indices generated from a ``Pose``. Nothing here
depends on Qt, so the frames can be checked in tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from functools import lru_cache

SIZE = 32
BASE = 30          # row of the soles of the feet (row 31 is the outline under them)
BODY_RX = 8        # grid half-width of the body, used for collision
BODY_H = 15        # grid height of the body without the sprout

# palette indices
T, OUTLINE, BODY, SHADE, BELLY, EYE, CHEEK, LEAF, LEAF_DARK, WHITE, ACC1, ACC2, GOLD = range(13)

Grid = tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class Pose:
    cx: float = 16.0
    rx: float = 8.0
    ry: float = 7.0
    lift: int = 0                       # body raised above the feet line
    feet: tuple[tuple[int, int], ...] = ((-4, 0), (4, 0))   # (dx, lift) per foot
    eyes: str = "open"                  # open | closed | happy | wide | dizzy | half
    look: int = 0
    arms: tuple[int, int] = (0, 0)      # (left, right): 0 down, 1 out, 2 up
    leaf: int = 0                       # sway in pixels
    droop: bool = False
    mouth: bool = False
    blush: bool = True
    emote: str = ""


EMOTES: dict[str, tuple[int, tuple[str, ...]]] = {
    "z":     (EYE,   ("###", "..#", ".#.", "###")),
    "zz":    (EYE,   ("...###", "....#.", "...###", "###...", ".#....", "###...")),
    "heart": (CHEEK, (".#.#.", "#####", "#####", ".###.", "..#..")),
    "!":     (ACC1,  ("##", "##", "##", "..", "##")),
    "?":     (EYE,   (".##.", "#..#", "..#.", "....", "..#.")),
    "star":  (GOLD,  ("..#..", ".###.", "#####", ".###.", ".#.#.")),
}

ACCESSORIES = ("none", "bow", "scarf", "glasses", "party_hat", "crown")


def _put(g: list[list[int]], x: int, y: int, c: int) -> None:
    if 0 <= x < SIZE and 0 <= y < SIZE:
        g[y][x] = c


def _stamp(g: list[list[int]], x: int, y: int, rows: tuple[str, ...], c: int) -> None:
    for j, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == "#":
                _put(g, x + i, y + j, c)


def render(pose: Pose, accessory: str = "none", emote: str = "", facing: int = 1) -> Grid:
    """The finished frame. Emotes are stamped after mirroring so "?" and "z" stay readable."""
    return _compose(pose, accessory, emote or pose.emote, facing)


@lru_cache(maxsize=None)
def _compose(pose: Pose, accessory: str, emote: str, facing: int) -> Grid:
    grid, top = _render(pose, accessory)
    rows = [list(r if facing > 0 else r[::-1]) for r in grid]
    if emote in EMOTES:
        colour, art = EMOTES[emote]
        _stamp(rows, SIZE - len(art[0]) - 1, max(0, top - 9), art, colour)
    return tuple(tuple(r) for r in rows)


@lru_cache(maxsize=None)
def _render(pose: Pose, accessory: str) -> tuple[Grid, int]:
    g = [[T] * SIZE for _ in range(SIZE)]
    cx = pose.cx
    icx = int(cx)
    bottom = BASE - 1 - pose.lift            # lowest body row
    cy = bottom + 1 - pose.ry                # ellipse centre (continuous)
    top = math.ceil(cy - pose.ry - 0.5)      # highest body row
    mid = int(cy)
    left_out = math.ceil(cx - pose.rx - 0.5) - 1
    right_out = math.floor(cx + pose.rx - 0.5) + 1

    for dx, lift in pose.feet:
        for i in range(-1, 2):
            _put(g, icx + dx + i - (1 if dx < 0 else 0), BASE - lift, SHADE)
            _put(g, icx + dx + i - (1 if dx < 0 else 0), BASE - lift - 1, SHADE)

    # body: soft shade on the underside, lighter belly, one highlight pixel
    for y in range(SIZE):
        for x in range(SIZE):
            nx, ny = (x + 0.5 - cx) / pose.rx, (y + 0.5 - cy) / pose.ry
            if nx * nx + ny * ny > 1.0:
                continue
            c = SHADE if (ny > 0.6 or nx * 0.55 + ny * 0.85 > 0.75) else BODY
            bx = (x + 0.5 - cx) / (pose.rx * 0.5)
            by = (y + 0.5 - (cy + pose.ry * 0.45)) / (pose.ry * 0.42)
            if bx * bx + by * by <= 1.0:
                c = BELLY
            g[y][x] = c
    _put(g, icx - int(pose.rx * 0.55) - 1, math.ceil(cy - pose.ry * 0.6), WHITE)

    for out, sign, arm in ((left_out, -1, pose.arms[0]), (right_out, 1, pose.arms[1])):
        if arm == 1:
            for i in range(2):
                _put(g, out + sign * i, mid + 1, BODY)
                _put(g, out + sign * i, mid + 2, SHADE)
        elif arm == 2:
            for j in range(4):
                _put(g, out, mid - 1 - j, BODY)
                _put(g, out + sign, mid - 2 - j, BODY)

    # face
    ey = math.floor(cy - pose.ry * 0.1)
    for sign in (-1, 1):
        ex = icx + pose.look + (-4 if sign < 0 else 2)      # left column of a 2-wide eye
        wide_x = ex - 1 if sign < 0 else ex                 # left column of a 3-wide eye
        e = pose.eyes
        if e in ("open", "wide"):
            h = 3 if e == "open" else 4
            for j in range(h):
                _put(g, ex, ey + 1 - j, EYE)
                _put(g, ex + 1, ey + 1 - j, EYE)
            _put(g, ex, ey + 2 - h, WHITE)
        elif e == "half":
            for i in range(2):
                _put(g, ex + i, ey, EYE)
                _put(g, ex + i, ey + 1, EYE)
                _put(g, ex + i, ey - 1, SHADE)
        elif e == "closed":
            for i in range(3):
                _put(g, wide_x + i, ey + 1, EYE)
        elif e == "happy":
            _put(g, wide_x, ey + 1, EYE)
            _put(g, wide_x + 1, ey, EYE)
            _put(g, wide_x + 2, ey + 1, EYE)
        elif e == "dizzy":
            for i, j in ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)):
                _put(g, wide_x + i, ey - 1 + j, EYE)
        if pose.blush:
            bx0 = ex - 2 if sign < 0 else ex + 2
            _put(g, bx0, ey + 3, CHEEK)
            _put(g, bx0 + 1, ey + 3, CHEEK)
    if pose.mouth:
        for i in (-1, 0):
            _put(g, icx + pose.look + i, ey + 3, EYE)
            _put(g, icx + pose.look + i, ey + 4, CHEEK)

    # sprout
    if pose.droop:
        for i in (-1, 0):
            _put(g, icx + i, top - 1, LEAF_DARK)
        _stamp(g, icx - 5, top - 1, (".###", "###."), LEAF)
        _stamp(g, icx + 1, top - 1, ("###.", ".###"), LEAF)
    else:
        lx = icx + pose.leaf
        for i in (-1, 0):
            _put(g, icx + i, top - 1, LEAF_DARK)
            _put(g, icx + i + pose.leaf // 2, top - 2, LEAF_DARK)
            _put(g, lx + i, top - 3, LEAF_DARK)
        _stamp(g, lx - 5, top - 5, (".##.", "####", ".###"), LEAF)
        _stamp(g, lx + 1, top - 5, (".##.", "####", "###."), LEAF)

    _accessory(g, accessory, icx, top, ey, mid, pose)

    # one-pixel outline around everything drawn so far
    out_grid = [row[:] for row in g]
    for y in range(SIZE):
        for x in range(SIZE):
            if g[y][x] == T and any(
                0 <= x + i < SIZE and 0 <= y + j < SIZE and g[y + j][x + i] != T
                for i, j in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ):
                out_grid[y][x] = OUTLINE

    return tuple(tuple(r) for r in out_grid), top


def _accessory(g: list[list[int]], name: str, icx: int, top: int, ey: int, mid: int, pose: Pose) -> None:
    if name == "bow":
        _stamp(g, icx - 8, top, ("#...#", "##.##", "#####", "##.##", "#...#"), ACC1)
        _put(g, icx - 6, top + 2, ACC2)
    elif name == "scarf":
        y = ey + 4
        for x in range(SIZE):
            if g[y][x] != T:
                g[y][x] = ACC1
                if g[y + 1][x] != T:
                    g[y + 1][x] = ACC2 if x % 3 == 0 else ACC1
        _stamp(g, icx + 3, y + 2, ("##", "##", "#."), ACC1)
    elif name == "glasses":
        for sign in (-1, 1):
            ex = icx + pose.look + (-4 if sign < 0 else 2)
            for i in range(-1, 3):
                _put(g, ex + i, ey - 2, EYE)
                _put(g, ex + i, ey + 2, EYE)
            for j in range(-1, 2):
                _put(g, ex - 1, ey + j, EYE)
                _put(g, ex + 2, ey + j, EYE)
        for i in (-1, 0):
            _put(g, icx + pose.look + i, ey - 1, EYE)
    elif name == "party_hat":
        _stamp(g, icx + 2, top - 5, ("..#..", "..#..", ".###.", ".###.", "#####", "#####"), ACC1)
        _put(g, icx + 4, top - 6, GOLD)
        _put(g, icx + 4, top - 2, ACC2)
        _put(g, icx + 3, top, ACC2)
        _put(g, icx + 5, top, ACC2)
    elif name == "crown":
        _stamp(g, icx + 2, top - 2, ("#.#.#", "#####", "#####"), GOLD)
        _put(g, icx + 4, top, ACC1)


# -- animations ---------------------------------------------------------------------------
P = Pose()
_breathe = replace(P, rx=8.4, ry=6.6)


def _walk(look: int, lean: int, ms: int, eyes: str = "open") -> list[tuple[Pose, int]]:
    a = replace(P, look=look, leaf=-lean, eyes=eyes)
    return [
        (replace(a, feet=((-4, 1), (4, 0)), lift=1), ms),
        (replace(a, feet=((-2, 0), (2, 0))), ms),
        (replace(a, feet=((-4, 0), (4, 1)), lift=1), ms),
        (replace(a, feet=((-2, 0), (2, 0))), ms),
    ]


_sit = replace(P, rx=8.6, ry=6.4, feet=((-6, 0), (6, 0)))
_sleep = replace(P, rx=9.6, ry=5.0, eyes="closed", droop=True, feet=((-7, 0), (7, 0)))
_air = replace(P, rx=7.2, ry=7.8, feet=((-3, 0), (3, 0)), lift=1)
_climb = replace(P, look=2, lift=1, leaf=-1)

# Frames face right; the UI mirrors them when the pet faces left.
ANIMATIONS: dict[str, list[tuple[Pose, int]]] = {
    "idle": [(P, 700), (_breathe, 700), (P, 700), (_breathe, 700), (P, 500),
             (replace(P, eyes="closed"), 130)],
    "look": [(replace(P, look=-2, leaf=1), 600), (replace(P, look=-2, eyes="half", leaf=1), 120),
             (P, 250), (replace(P, look=2, leaf=-1), 600), (P, 250)],
    "walk": _walk(1, 1, 150),
    "run": _walk(2, 2, 80, "happy"),
    "sit": [(_sit, 900), (replace(_sit, rx=8.9, ry=6.1), 900), (_sit, 900), (replace(_sit, eyes="closed"), 140)],
    "sleep": [(replace(_sleep, emote="z"), 1100), (replace(_sleep, rx=9.9, ry=4.7, emote="zz"), 1100)],
    "jump": [(replace(_air, eyes="happy", arms=(2, 2)), 200)],
    "fall": [(replace(_air, eyes="wide", arms=(2, 2), mouth=True, leaf=-1), 110),
             (replace(_air, eyes="wide", arms=(2, 2), mouth=True, leaf=1, feet=((-4, 0), (4, 1))), 110)],
    "land": [(replace(P, rx=10.0, ry=5.0, eyes="closed", feet=((-6, 0), (6, 0)), droop=True), 250)],
    "climb": [(replace(_climb, arms=(1, 2), feet=((-3, 1), (4, 0))), 180),
              (replace(_climb, arms=(1, 1), lift=2), 180),
              (replace(_climb, arms=(2, 1), feet=((-3, 0), (4, 1))), 180),
              (replace(_climb, arms=(1, 1), lift=2), 180)],
    "hang": [(replace(_climb, arms=(1, 2), eyes="half"), 900), (replace(_climb, arms=(1, 2), look=0), 900)],
    "dragged": [(replace(_air, eyes="wide", arms=(1, 1), feet=((-3, 0), (3, 1))), 160),
                (replace(_air, eyes="wide", arms=(1, 1), feet=((-3, 1), (3, 0))), 160)],
    "celebrate": [(replace(P, rx=9.0, ry=6.0, eyes="happy"), 110),
                  (replace(P, lift=3, feet=((-4, 2), (4, 2)), eyes="happy", arms=(2, 2), emote="star"), 130),
                  (replace(P, lift=5, feet=((-3, 4), (3, 4)), eyes="happy", arms=(2, 2), mouth=True, emote="star"), 150),
                  (replace(P, lift=2, feet=((-4, 1), (4, 1)), eyes="happy", arms=(2, 2), emote="star"), 110)],
    "wave": [(replace(P, eyes="happy", arms=(0, 2), emote="!"), 220),
             (replace(P, eyes="happy", arms=(0, 1), emote="!"), 220)],
    "dizzy": [(replace(P, cx=15.0, eyes="dizzy", droop=True, blush=False, emote="?"), 260),
              (replace(P, cx=17.0, eyes="dizzy", droop=True, blush=False, emote="?"), 260)],
    "petted": [(replace(P, rx=8.6, ry=6.4, eyes="happy", emote="heart"), 200),
               (replace(P, eyes="happy", lift=1, emote="heart"), 200)],
}

ICON_POSE = replace(P, eyes="happy")
