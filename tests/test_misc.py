import json

from pixelpal.config import Automation, Config, QuickAction, config_dir
from pixelpal.core.geometry import Rect
from pixelpal.platform.base import Platform, ScreenScale, get_platform, native_to_logical
from pixelpal.platform.win32 import acceptable
from pixelpal.sprites import pip
from pixelpal.sprites.palette import make_palette, parse_hex


# -- config -----------------------------------------------------------------------------------
def test_config_round_trip(tmp_path):
    path = tmp_path / "c.json"
    cfg = Config(scale=4, quiet_mode=True, body_colour="#112233")
    cfg.quick_actions = [QuickAction("Site", "url", "https://example.com")]
    auto = Automation("a", "echo hi")
    auto.approve()
    cfg.automations = [auto]
    cfg.save(path)
    loaded = Config.load(path)
    assert loaded == cfg and loaded.automations[0].approved


def test_config_survives_garbage(tmp_path):
    path = tmp_path / "c.json"
    assert Config.load(path) == Config()                      # missing file
    path.write_text("{not json")
    assert Config.load(path) == Config()
    path.write_text(json.dumps({"scale": 99, "activity": "fast", "quick_actions": [{"name": "x"}],
                                "chattiness": 7, "unknown_key": 1, "quiet_mode": 1}))
    cfg = Config.load(path)
    assert cfg.scale == 8 and cfg.activity == 0.6 and cfg.chattiness == 1.0 and cfg.quiet_mode is True
    assert cfg.quick_actions == Config().quick_actions


def test_hand_edited_command_loses_approval(tmp_path):
    path = tmp_path / "c.json"
    cfg = Config()
    auto = Automation("a", "echo hi")
    auto.approve()
    cfg.automations = [auto]
    cfg.save(path)
    raw = json.loads(path.read_text())
    raw["automations"][0]["command"] = "format c:"
    path.write_text(json.dumps(raw))
    assert not Config.load(path).automations[0].approved


def test_config_dir_is_overridable(tmp_path):
    assert config_dir() == tmp_path / "home"


# -- platform ---------------------------------------------------------------------------------
def test_native_to_logical_single_scaled_monitor():
    screens = [ScreenScale(Rect(0, 0, 1280, 720), 1.5)]            # a 1920x1080 panel at 150%
    assert native_to_logical(Rect(300, 150, 1500, 900), screens) == Rect(200, 100, 1000, 600)


def test_native_to_logical_mixed_dpi_monitors():
    # Left: 1920x1080 at 100%. Right: 3840x2160 at 200%, physically starting at x=1920.
    screens = [ScreenScale(Rect(0, 0, 1920, 1080), 1.0), ScreenScale(Rect(1920, 0, 3840, 1080), 2.0)]
    assert native_to_logical(Rect(100, 100, 500, 400), screens) == Rect(100, 100, 500, 400)
    assert native_to_logical(Rect(2920, 200, 4920, 1200), screens) == Rect(2420, 100, 3420, 600)
    assert native_to_logical(Rect(1, 2, 3, 4), []) == Rect(1, 2, 3, 4)


def test_window_filter():
    r = Rect(0, 0, 800, 600)
    ok = dict(visible=True, minimized=False, cloaked=False, tool=False, title="Notepad",
              cls="Notepad", own=False, rect=r)
    assert acceptable(**ok)
    for change in ({"visible": False}, {"minimized": True}, {"cloaked": True}, {"tool": True},
                   {"own": True}, {"title": ""}, {"cls": "Shell_TrayWnd"}, {"rect": Rect(0, 0, 50, 20)}):
        assert not acceptable(**{**ok, **change}), change


def test_generic_platform_is_a_safe_fallback():
    p = Platform()
    assert p.list_windows() == [] and not p.autostart_enabled() and p.sample_system().cpu_percent is None
    assert get_platform().name in ("generic", "windows")


# -- sprites ----------------------------------------------------------------------------------
def test_every_animation_frame_is_a_well_formed_sprite():
    assert set(pip.ANIMATIONS) >= {"idle", "look", "walk", "run", "sit", "sleep", "jump", "fall", "land",
                                   "climb", "hang", "dragged", "celebrate", "wave", "dizzy", "petted"}
    for name, frames in pip.ANIMATIONS.items():
        for pose, ms in frames:
            grid = pip.render(pose)
            assert ms > 0 and len(grid) == pip.SIZE and all(len(r) == pip.SIZE for r in grid)
            filled = sum(c != pip.T for row in grid for c in row)
            assert 150 < filled < 600, name
            assert any(c == pip.EYE for row in grid for c in row), name
            # Drawn pixels never touch the left/right/top canvas border, so the outline is complete.
            assert all(row[0] == pip.T and row[-1] == pip.T for row in grid), name
            assert all(c == pip.T for c in grid[0]), name


def test_grounded_frames_stand_on_the_floor_line():
    for name in ("idle", "walk", "sit", "sleep", "land"):
        for pose, _ in pip.ANIMATIONS[name]:
            grid = pip.render(pose)
            assert any(c == pip.SHADE for c in grid[pip.BASE]), name      # a foot on the sole row
            assert all(c in (pip.T, pip.OUTLINE) for c in grid[pip.BASE + 1]), name


def test_accessories_and_emotes_change_the_sprite():
    plain = pip.render(pip.P)
    for acc in pip.ACCESSORIES[1:]:
        assert pip.render(pip.P, acc) != plain, acc
    for emote in pip.EMOTES:
        assert pip.render(pip.P, "none", emote) != plain, emote


def test_palette_follows_body_colour():
    pal = make_palette("#ff8800")
    assert len(pal) == 13 and pal[pip.T][3] == 0 and pal[pip.BODY] == (255, 136, 0, 255)
    assert sum(pal[pip.SHADE][:3]) < sum(pal[pip.BODY][:3]) < sum(pal[pip.BELLY][:3])
    assert parse_hex("nonsense") == parse_hex("#8fd9a8")
