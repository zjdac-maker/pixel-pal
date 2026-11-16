"""Modular abilities. To add one: subclass ``Ability`` and add it to ``default_abilities``."""
from __future__ import annotations

from .automations import AutomationAbility
from .base import Ability, AbilityContext, MenuItem
from .launcher import LauncherAbility
from .sysmon import SystemMonitorAbility
from .timers import TimerAbility


def default_abilities() -> list[Ability]:
    return [LauncherAbility(), TimerAbility(), AutomationAbility(), SystemMonitorAbility()]


__all__ = ["Ability", "AbilityContext", "MenuItem", "default_abilities"]
