"""User-approved scripts and shortcuts.

Safety model:
* A command only runs if the user approved that exact text in a dialog. The approval is a
  hash of the command, so editing it (in Settings or in the JSON file) revokes it.
* Commands are started directly, never through a shell, so ``&&``, pipes and redirects in
  the text are not interpreted.
* Nothing ever runs elevated; the process simply inherits the user's own rights.
"""
from __future__ import annotations

import shlex
import subprocess
import sys
import threading
from typing import Callable

from ..config import Automation
from .base import Ability, MenuItem

TIMEOUT = 15 * 60


def build_args(command: str) -> list[str] | str:
    """Windows hands the string to CreateProcess untouched; elsewhere split it ourselves."""
    return command if sys.platform == "win32" else shlex.split(command)


def run_command(command: str, timeout: float = TIMEOUT) -> tuple[bool, str]:
    """Run without a shell and report (succeeded, short detail)."""
    try:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        proc = subprocess.run(build_args(command), shell=False, capture_output=True, text=True,
                              timeout=timeout, creationflags=flags, stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return False, "it took too long"
    except (OSError, ValueError) as exc:
        return False, str(exc) or type(exc).__name__
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        return False, f"exit code {proc.returncode}" + (f": {tail[-1][:80]}" if tail else "")
    return True, ""


class AutomationAbility(Ability):
    name = "automations"

    def setup(self, ctx) -> None:
        super().setup(ctx)
        self.running: set[str] = set()

    def menu(self) -> list[MenuItem]:
        items = []
        for a in self.ctx.config.automations:
            label = a.name if a.approved else f"{a.name} (needs approval)"
            items.append(MenuItem(label, lambda a=a: self.run(a), enabled=a.name not in self.running))
        if not items:
            items = [MenuItem("(add some in Settings)", enabled=False)]
        return [MenuItem("Automations", children=items)]

    def run(self, automation: Automation, on_done: Callable[[bool], None] | None = None) -> bool:
        """Start an automation. Returns False if it was not started."""
        if not automation.approved:
            ok = self.ctx.confirm(
                "Approve automation",
                f"Allow pixel-pal to run this command whenever you pick “{automation.name}”?\n\n"
                f"{automation.command}\n\nOnly approve commands you wrote or fully understand.")
            if not ok:
                return False
            automation.approve()
            self.ctx.save()
        if automation.name in self.running:
            return False
        self.running.add(automation.name)
        self.ctx.say(f"Running {automation.name}…", 2.5)
        command, name = automation.command, automation.name

        def work() -> None:
            ok, detail = run_command(command)

            def finish() -> None:
                self.running.discard(name)
                if ok:
                    self.ctx.celebrate(f"{name} finished!")
                else:
                    self.ctx.confuse(f"{name} failed ({detail}).")
                if on_done:
                    on_done(ok)

            self.ctx.run_later(finish)

        threading.Thread(target=work, name=f"automation-{name}", daemon=True).start()
        return True
