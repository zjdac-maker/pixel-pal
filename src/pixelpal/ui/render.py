"""Turns palette-index grids into crisp, cached QPixmaps."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QImage, QPixmap, qRgba

from ..sprites import pip
from ..sprites.palette import make_palette


class SpriteRenderer:
    def __init__(self, body_colour: str, scale: int) -> None:
        self._cache: dict[tuple, QPixmap] = {}
        self.configure(body_colour, scale)

    def configure(self, body_colour: str, scale: int) -> None:
        self.scale = scale
        self.palette = [qRgba(*c) for c in make_palette(body_colour)]
        self._cache.clear()

    @property
    def logical_size(self) -> int:
        return pip.SIZE * self.scale

    def image(self, pose: pip.Pose, accessory: str = "none", facing: int = 1) -> QImage:
        grid = pip.render(pose, accessory, facing=facing)
        img = QImage(pip.SIZE, pip.SIZE, QImage.Format.Format_ARGB32)
        for y, row in enumerate(grid):
            for x, c in enumerate(row):
                img.setPixel(x, y, self.palette[c])
        return img

    def pixmap(self, pose: pip.Pose, accessory: str, facing: int, dpr: float) -> QPixmap:
        key = (pose, accessory, facing, round(dpr * 100))
        pm = self._cache.get(key)
        if pm is None:
            img = self.image(pose, accessory, facing)
            px = max(pip.SIZE, round(self.logical_size * dpr))
            # Nearest-neighbour keeps the pixel edges sharp at every DPI.
            img = img.scaled(px, px, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            pm = QPixmap.fromImage(img)
            pm.setDevicePixelRatio(px / self.logical_size)
            self._cache[key] = pm
        return pm

    def icon(self) -> QIcon:
        img = self.image(pip.ICON_POSE).copy(4, 8, 24, 24)
        return QIcon(QPixmap.fromImage(img.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.FastTransformation)))
