"""Frame timing. An animation is a list of (frame_key, milliseconds)."""
from __future__ import annotations


class Animator:
    def __init__(self, animations: dict[str, list[tuple[object, int]]]) -> None:
        self.animations = animations
        self.name = next(iter(animations))
        self.index = 0
        self._elapsed = 0.0

    def play(self, name: str) -> None:
        if name != self.name and name in self.animations:
            self.name, self.index, self._elapsed = name, 0, 0.0

    def update(self, dt: float) -> bool:
        """Advance time; returns True when the visible frame changed."""
        frames = self.animations[self.name]
        self._elapsed += dt * 1000.0
        changed = False
        while self._elapsed >= frames[self.index][1]:
            self._elapsed -= frames[self.index][1]
            self.index = (self.index + 1) % len(frames)
            changed = True
        return changed

    @property
    def frame(self) -> object:
        return self.animations[self.name][self.index][0]
