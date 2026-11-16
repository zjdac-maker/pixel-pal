import sys
import threading
import time

import pytest

from pixelpal.abilities.automations import AutomationAbility, run_command
from pixelpal.abilities.launcher import LauncherAbility, validate
from pixelpal.abilities.sysmon import SystemMonitorAbility
from pixelpal.abilities.timers import TimerAbility
from pixelpal.config import Automation, Config, QuickAction
from pixelpal.core.sysmon import Sample, SystemWatcher
from pixelpal.core.timers import TimerManager, format_remaining
from pixelpal.platform.base import Platform


class FakePlatform(Platform):
    def __init__(self):
        self.opened, self.sample = [], Sample()

    def open_path(self, target):
        self.opened.append(target)

    def sample_system(self):
        return self.sample


class FakeContext:
    def __init__(self):
        self.config, self.platform = Config(), FakePlatform()
        self.log, self.answers, self.saves = [], {}, 0
        self.done = threading.Event()

    def say(self, text, seconds=4.0, important=False): self.log.append(("say", text))
    def celebrate(self, text=""): self.log.append(("celebrate", text))
    def alert(self, text): self.log.append(("alert", text))
    def confuse(self, text=""): self.log.append(("confuse", text))
    def save(self): self.saves += 1
    def ask_number(self, *a): return self.answers.get("number")
    def ask_text(self, *a): return self.answers.get("text")
    def confirm(self, title, text): self.log.append(("confirm", text)); return self.answers.get("confirm", False)
    def run_later(self, fn): fn(); self.done.set()

    def kinds(self): return [k for k, _ in self.log]


# -- timers ---------------------------------------------------------------------------------
def test_timer_manager_fires_in_order_and_persists():
    now = [1000.0]
    m = TimerManager(lambda: now[0])
    a = m.start("countdown", 60, "tea")
    m.start("reminder", 30, "stretch")
    assert m.poll() == []
    now[0] += 45
    assert [t.label for t in m.poll()] == ["stretch"]
    restored = TimerManager(lambda: now[0])
    restored.load(m.dump() + [{"broken": True}])
    assert restored.timers == [a]
    assert restored.start("break", 5).id == a.id + 1
    now[0] += 100
    assert [t.label for t in restored.poll()] == ["", "tea"]      # the 5 s break was due first
    with pytest.raises(ValueError):
        m.start("countdown", 0)


def test_format_remaining():
    assert format_remaining(59.6) == "1:00"
    assert format_remaining(3725) == "1:02:05"


def test_pomodoro_celebrates_then_starts_a_break(monkeypatch):
    ctx, ability = FakeContext(), TimerAbility()
    ability.setup(ctx)
    now = [5000.0]
    ability.manager.clock = lambda: now[0]
    ability.start_pomodoro()
    assert ability.focus_active and ctx.config.timers and ctx.saves == 1
    now[0] += 25 * 60 + 1
    ability.tick(now[0])
    assert ctx.kinds()[-1] == "celebrate"
    assert [t.kind for t in ability.manager.timers] == ["break"] and not ability.focus_active
    now[0] += 5 * 60 + 1
    ability.tick(now[0])
    assert ctx.kinds()[-1] == "alert" and ability.manager.timers == []


def test_reminder_survives_restart():
    ctx, ability = FakeContext(), TimerAbility()
    ability.setup(ctx)
    ctx.answers = {"text": "call mum", "number": 10}
    ability.ask_reminder()
    again = TimerAbility()
    again.setup(ctx)                       # same config, as after a restart
    again.manager.clock = lambda: time.time() + 601
    again.tick(0)
    assert ("alert", "Reminder: call mum") in ctx.log
    labels = [i.label for i in again.menu()[0].children]
    assert labels[0].startswith("Pomodoro")


# -- system monitor ---------------------------------------------------------------------------
def test_battery_alert_once_until_recharged():
    w = SystemWatcher(battery_threshold=20)
    assert w.feed(Sample(battery_percent=50, on_ac=False), 0) == []
    assert [a.kind for a in w.feed(Sample(battery_percent=19, on_ac=False), 1)] == ["low_battery"]
    assert w.feed(Sample(battery_percent=15, on_ac=False), 2) == []          # no nagging
    assert w.feed(Sample(battery_percent=18, on_ac=True), 3) == []           # plugged in: re-arm
    assert len(w.feed(Sample(battery_percent=17, on_ac=False), 4)) == 1


def test_cpu_alert_needs_sustained_load_and_cools_down():
    w = SystemWatcher(cpu_threshold=90, cpu_sustain=3, cpu_cooldown=100)
    hot, t = Sample(cpu_percent=97), 0
    assert w.feed(hot, 0) == [] and w.feed(Sample(cpu_percent=10), 1) == []  # a spike is ignored
    out = [w.feed(hot, t) for t in range(2, 5)]
    assert [len(o) for o in out] == [0, 0, 1] and out[-1][0].value == 97
    assert all(w.feed(hot, t) == [] for t in range(5, 50))                   # cooldown
    assert any(w.feed(hot, t) for t in range(105, 110))


def test_monitor_ability_uses_config_thresholds():
    ctx, ability = FakeContext(), SystemMonitorAbility()
    ability.setup(ctx)
    ctx.config.battery_threshold = 40
    ctx.platform.sample = Sample(battery_percent=35, on_ac=False)
    ability.tick(100.0)
    assert ctx.kinds() == ["alert"] and "35%" in ctx.log[0][1]
    ctx.config.monitor_system = False
    ctx.platform.sample = Sample(battery_percent=1, on_ac=False)
    ability.tick(200.0)
    assert len(ctx.log) == 1


# -- launcher -----------------------------------------------------------------------------------
def test_launcher_validates_targets(tmp_path):
    assert validate(QuickAction("x", "url", "https://example.com")) is None
    assert validate(QuickAction("x", "url", "file:///etc/passwd")) is not None
    assert validate(QuickAction("x", "url", "javascript:alert(1)")) is not None
    assert validate(QuickAction("x", "folder", str(tmp_path))) is None
    assert validate(QuickAction("x", "folder", str(tmp_path / "nope"))) is not None
    assert validate(QuickAction("x", "app", "  ")) is not None
    assert validate(QuickAction("x", "script", "a")) is not None


def test_launcher_opens_and_reports(tmp_path, monkeypatch):
    ctx, ability = FakeContext(), LauncherAbility()
    ability.setup(ctx)
    opened_urls = []
    monkeypatch.setattr("webbrowser.open", opened_urls.append)
    assert ability.run(QuickAction("Docs", "folder", str(tmp_path)))
    assert ability.run(QuickAction("Site", "url", "https://example.com"))
    assert ctx.platform.opened == [str(tmp_path)] and opened_urls == ["https://example.com"]
    assert not ability.run(QuickAction("Bad", "url", "ftp://x"))
    assert ctx.kinds() == ["say", "say", "confuse"]
    assert [i.label for i in ability.menu()[0].children] == ["Notepad", "Calculator", "Downloads folder"]


# -- automations ------------------------------------------------------------------------------
PY = f'"{sys.executable}"'


def test_approval_is_tied_to_the_exact_command():
    a = Automation("backup", "robocopy a b")
    assert not a.approved
    a.approve()
    assert a.approved
    a.command += " /purge"
    assert not a.approved                     # editing revokes approval
    assert not Automation("empty", "   ", Automation.digest("   ")).approved


def test_run_command_reports_success_and_failure():
    assert run_command(f'{PY} -c "print(1)"') == (True, "")
    ok, detail = run_command(f'{PY} -c "import sys; sys.exit(3)"')
    assert not ok and "exit code 3" in detail
    ok, detail = run_command("definitely-not-a-real-program-xyz")
    assert not ok and detail
    assert run_command(f'{PY} -c "import time; time.sleep(5)"', timeout=0.2) == (False, "it took too long")


def test_shell_syntax_is_not_interpreted(tmp_path):
    marker = tmp_path / "pwned"
    run_command(f'{PY} -c "print(1)" && {PY} -c "open(r\'{marker}\', \'w\')"')
    run_command(f'{PY} -c "print(1)" > {marker}')
    assert not marker.exists()


def test_unapproved_automation_asks_first_and_can_be_refused():
    ctx, ability = FakeContext(), AutomationAbility()
    ability.setup(ctx)
    auto = Automation("hello", f'{PY} -c "print(1)"')
    ctx.config.automations.append(auto)
    assert not ability.run(auto)
    assert ctx.kinds() == ["confirm"] and auto.command in ctx.log[0][1] and not auto.approved
    assert ability.menu()[0].children[0].label == "hello (needs approval)"


def test_approved_automation_runs_and_celebrates():
    ctx, ability = FakeContext(), AutomationAbility()
    ability.setup(ctx)
    auto = Automation("hello", f'{PY} -c "print(1)"')
    ctx.answers["confirm"] = True
    assert ability.run(auto)
    assert ctx.done.wait(20)
    assert auto.approved and ctx.saves == 1
    assert ctx.kinds() == ["confirm", "say", "celebrate"] and not ability.running
    ctx.done.clear()
    assert ability.run(auto)                  # second run: no new prompt
    assert ctx.done.wait(20) and ctx.kinds().count("confirm") == 1


def test_failed_automation_confuses_the_pet():
    ctx, ability = FakeContext(), AutomationAbility()
    ability.setup(ctx)
    auto = Automation("boom", f'{PY} -c "raise SystemExit(2)"')
    auto.approve()
    assert ability.run(auto) and ctx.done.wait(20)
    assert ctx.kinds() == ["say", "confuse"] and "exit code 2" in ctx.log[-1][1]
