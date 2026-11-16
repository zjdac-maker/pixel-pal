"""Builds the 13-colour palette for a character from one body colour (pure Python)."""
from __future__ import annotations

import colorsys

RGB = tuple[int, int, int]


def parse_hex(value: str, fallback: RGB = (143, 217, 168)) -> RGB:
    v = value.strip().lstrip("#")
    if len(v) != 6:
        return fallback
    try:
        return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16)
    except ValueError:
        return fallback


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))  # type: ignore[return-value]


def _shade(c: RGB) -> RGB:
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in c))
    r, g, b = colorsys.hls_to_rgb((h + 0.03) % 1.0, max(0.0, l * 0.74), min(1.0, s * 1.05))
    return round(r * 255), round(g * 255), round(b * 255)


def make_palette(body_hex: str) -> list[tuple[int, int, int, int]]:
    """RGBA for each palette index used by ``sprites.pip``."""
    body = parse_hex(body_hex)
    solid = [
        (59, 42, 63),                    # outline
        body,
        _shade(body),
        _mix(body, (255, 255, 255), 0.68),   # belly
        (43, 34, 51),                    # eye
        (255, 140, 155),                 # cheek
        (108, 194, 74),                  # leaf
        (63, 143, 58),                   # leaf dark
        (255, 255, 255),
        (255, 93, 115),                  # accessory 1
        (255, 209, 220),                 # accessory 2
        (255, 204, 51),                  # gold
    ]
    return [(0, 0, 0, 0)] + [(r, g, b, 255) for r, g, b in solid]
