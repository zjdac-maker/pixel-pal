"""The contract between the pet and the useful things it can do."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

from ..config import Config
from ..platform.base import Platform


@dataclass
class MenuItem:
    label: str
    action: Callable[[], None] | None = None
    children: list["MenuItem"] = field(default_factory=list)
    enabled: bool = True
    separator: bool = False
    checked: bool | None = None      # None = not a checkable entry


class AbilityContext(Protocol):
    """What an ability may ask of the pet. Implemented by the app controller."""
    config: Config
    platform: Platform

    def say(self, text: str, seconds: float = 4.0, important: bool = False) -> None: ...
    def celebrate(self, text: str = "") -> None: ...          # also counts towards rewards
    def alert(self, text: str) -> None: ...
    def confuse(self, text: str = "") -> None: ...
    def save(self) -> None: ...
    def ask_number(self, title: str, label: str, default: int, lo: int, hi: int) -> int | None: ...
    def ask_text(self, title: str, label: str, default: str = "") -> str | None: ...
    def confirm(self, title: str, text: str) -> bool: ...
    def run_later(self, fn: Callable[[], None]) -> None: ...  # marshal a call onto the UI thread


class Ability:
    name = "ability"

    def setup(self, ctx: AbilityContext) -> None:
        self.ctx = ctx

    def menu(self) -> list[MenuItem]:
        """Entries for the right-click / tray menu."""
        return []

    def tick(self, now: float) -> None:
        """Called about once a second."""

    def shutdown(self) -> None:
        """Called once before the app exits."""
