"""Local settings and persistence (a single JSON file, no network, no registry)."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

COLOUR_PRESETS = {
    "Mint": "#8fd9a8",
    "Peach": "#ffb38a",
    "Sky": "#8ec9f5",
    "Lavender": "#c3a6f0",
    "Lemon": "#f2dc6b",
    "Rose": "#f59ab5",
}


def config_dir() -> Path:
    override = os.environ.get("PIXELPAL_HOME")
    if override:
        return Path(override)
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "pixel-pal"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "pixel-pal"


@dataclass
class QuickAction:
    name: str
    kind: str        # app | folder | url
    target: str


@dataclass
class Automation:
    name: str
    command: str
    approved_hash: str = ""     # sha256 of the exact command the user approved

    @staticmethod
    def digest(command: str) -> str:
        return hashlib.sha256(command.encode("utf-8")).hexdigest()

    @property
    def approved(self) -> bool:
        return bool(self.command.strip()) and self.approved_hash == self.digest(self.command)

    def approve(self) -> None:
        self.approved_hash = self.digest(self.command)


def _default_actions() -> list[QuickAction]:
    return [
        QuickAction("Notepad", "app", "notepad.exe"),
        QuickAction("Calculator", "app", "calc.exe"),
        QuickAction("Downloads folder", "folder", "~/Downloads"),
    ]


@dataclass
class Config:
    scale: int = 3                      # screen pixels per sprite pixel
    body_colour: str = "#8fd9a8"
    accessory: str = "none"
    activity: float = 0.6
    chattiness: float = 0.5
    quiet_mode: bool = False
    speech_bubbles: bool = True
    follow_cursor: bool = True
    climbing: bool = True
    window_interaction: bool = True
    hide_in_fullscreen: bool = True
    monitor_system: bool = True
    battery_threshold: int = 20
    cpu_threshold: int = 90
    pomodoro_minutes: int = 25
    break_minutes: int = 5
    auto_break: bool = True
    tasks_done: int = 0
    quick_actions: list[QuickAction] = field(default_factory=_default_actions)
    automations: list[Automation] = field(default_factory=list)
    timers: list[dict] = field(default_factory=list)

    # -- persistence --------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or config_dir() / "config.json"
        cfg = cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cfg
        if not isinstance(raw, dict):
            return cfg
        for f in fields(cls):
            if f.name not in raw:
                continue
            value, default = raw[f.name], getattr(cfg, f.name)
            try:
                if f.name == "quick_actions":
                    value = [QuickAction(str(a["name"]), str(a["kind"]), str(a["target"])) for a in value]
                elif f.name == "automations":
                    value = [Automation(str(a["name"]), str(a["command"]), str(a.get("approved_hash", "")))
                             for a in value]
                elif isinstance(default, bool):
                    value = bool(value)
                elif isinstance(default, (int, float)):
                    value = type(default)(value)
                elif isinstance(default, str):
                    value = str(value)
                elif not isinstance(value, list):
                    continue
            except (KeyError, TypeError, ValueError):
                continue        # a damaged entry falls back to its default
            setattr(cfg, f.name, value)
        cfg.scale = max(2, min(8, cfg.scale))
        cfg.activity = max(0.0, min(1.0, cfg.activity))
        cfg.chattiness = max(0.0, min(1.0, cfg.chattiness))
        return cfg

    def save(self, path: Path | None = None) -> None:
        path = path or config_dir() / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(asdict(self), fh, indent=2)
            os.replace(tmp, path)       # atomic: a crash never leaves half a file
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
