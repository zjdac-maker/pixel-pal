"""Quick actions: open apps, folders and websites the user has configured."""
from __future__ import annotations

import os
import webbrowser
from urllib.parse import urlparse

from ..config import QuickAction
from .base import Ability, MenuItem


def validate(action: QuickAction) -> str | None:
    """Return a problem description, or None when the action is fine to run."""
    target = action.target.strip()
    if not target:
        return "nothing to open"
    if action.kind == "url":
        if urlparse(target).scheme not in ("http", "https"):
            return "only http(s) links can be opened"
    elif action.kind == "folder":
        if not os.path.isdir(os.path.expandvars(os.path.expanduser(target))):
            return "that folder does not exist"
    elif action.kind != "app":
        return f"unknown kind: {action.kind}"
    return None


class LauncherAbility(Ability):
    name = "launcher"

    def menu(self) -> list[MenuItem]:
        items = [MenuItem(a.name, lambda a=a: self.run(a)) for a in self.ctx.config.quick_actions]
        if not items:
            items = [MenuItem("(add some in Settings)", enabled=False)]
        return [MenuItem("Open", children=items)]

    def run(self, action: QuickAction) -> bool:
        problem = validate(action)
        if problem:
            self.ctx.confuse(f"I can't open {action.name}: {problem}.")
            return False
        try:
            if action.kind == "url":
                webbrowser.open(action.target.strip())
            else:
                self.ctx.platform.open_path(os.path.expandvars(os.path.expanduser(action.target.strip())))
        except Exception as exc:
            self.ctx.confuse(f"I couldn't open {action.name}. ({type(exc).__name__})")
            return False
        self.ctx.say(f"Opening {action.name}!", 2.5)
        return True
