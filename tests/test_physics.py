import random

import pytest

from pixelpal.core import physics
from pixelpal.core.behavior import Action, Brain, BrainSettings
from pixelpal.core.geometry import Rect
from pixelpal.core.mood import MoodState
from pixelpal.core.physics import Body, Mode, plan_jump, step
from pixelpal.core.world import ScreenInfo, WindowInfo, World

DT = 1 / 60


def run(body, world, seconds, stop=None):
    events = []
    for _ in range(int(seconds / DT)):
        events += step(body, world, DT)
        if stop and any(e.kind == stop for e in events):
            break
    return events


def test_falls_and_lands_on_the_taskbar_line(screen):
    world = World.build([screen])
    body = Body(x=500, y=100)
    events = run(body, world, 5)
    assert body.mode is Mode.GROUND and body.y == 1040
    assert [e.kind for e in events] == ["landed"]


def test_lands_on_a_window_top(world):
    body = Body(x=700, y=100)
    run(body, world, 5)
    assert body.mode is Mode.GROUND and body.y == 300 and body.floor.owner == 1


def test_fast_fall_does_not_tunnel_through_a_floor(world):
    body = Body(x=700, y=100, vy=1400)
    step(body, world, 0.2)          # one huge step straight past the window top
    assert body.y == 300


def test_rides_a_moving_window(screen):
    world = World.build([screen], [WindowInfo(1, Rect(400, 300, 1000, 700))])
    body = Body(x=700, y=100)
    run(body, world, 5)
    moved = World.build([screen], [WindowInfo(1, Rect(450, 250, 1050, 650))])
    step(body, moved, DT)
    assert (body.x, body.y, body.mode) == (750, 250, Mode.GROUND)


def test_falls_when_the_window_closes_or_minimises(screen, world):
    body = Body(x=700, y=100)
    run(body, world, 5)
    empty = World.build([screen])
    assert [e.kind for e in step(body, empty, DT)] == ["lost_surface"]
    run(body, empty, 5)
    assert body.y == 1040


def test_stops_at_a_ledge_or_walks_off(world):
    body = Body(x=700, y=100)
    run(body, world, 5)
    body.vx, body.avoid_edges = 200, True
    assert "edge" in [e.kind for e in run(body, world, 5, stop="edge")]
    assert body.x == 1000 and body.mode is Mode.GROUND
    body.avoid_edges = False
    assert "fell_off" in [e.kind for e in run(body, world, 1, stop="fell_off")]
    body.vx = 0
    run(body, world, 5)
    assert body.y == 1040


def test_screen_edge_stops_walking(screen):
    world = World.build([screen])
    body = Body(x=100, y=100)
    run(body, world, 5)
    body.vx = -300
    events = run(body, world, 3)
    assert body.x == body.half_w            # whole sprite stays on screen
    assert events[-1].kind == "hit_wall" and events[-1].wall.side == 1


def test_walks_across_monitors():
    a = ScreenInfo(Rect(0, 0, 1000, 800), Rect(0, 0, 1000, 760))
    b = ScreenInfo(Rect(1000, 0, 2000, 800), Rect(1000, 0, 2000, 760))
    world = World.build([a, b])
    body = Body(x=900, y=100)
    run(body, world, 5)
    body.vx = 300
    run(body, world, 2)
    assert body.x > 1200 and body.mode is Mode.GROUND and body.floor.x1 == 1000


def test_climbs_a_window_side_and_reaches_the_top(world):
    body = Body(x=300, y=600)
    wall = next(w for w in world.walls if w.owner == 1 and w.side == -1)
    body.attach_wall(wall, world)
    assert body.x == 400 - body.half_w and body.facing == 1
    body.vy = -100
    events = run(body, world, 10, stop="wall_top")
    assert events[-1].kind == "wall_top" and body.y - body.height == 300


def test_climbing_follows_a_dragged_window(screen, world):
    body = Body(x=300, y=600)
    body.attach_wall(next(w for w in world.walls if w.owner == 1 and w.side == 1), world)
    moved = World.build([screen], [WindowInfo(1, Rect(500, 350, 1100, 750))])
    step(body, moved, DT)
    assert body.mode is Mode.WALL and body.x == 1100 + body.half_w and body.y == 650


def test_respawns_when_its_monitor_disappears():
    a = ScreenInfo(Rect(0, 0, 1000, 800), Rect(0, 0, 1000, 760))
    b = ScreenInfo(Rect(1000, 0, 2000, 800), Rect(1000, 0, 2000, 760))
    body = Body(x=1700, y=100)
    run(body, World.build([a, b]), 5)
    only_a = World.build([a])
    events = run(body, only_a, 5)
    assert "respawn" in [e.kind for e in events]
    assert 0 <= body.x <= 1000 and body.y == 760


def test_plan_jump_lands_on_target(world):
    body = Body(x=200, y=700)
    v = plan_jump(body, 500, 300)
    assert v is not None
    body.launch(*v)
    run(body, world, 5, stop="landed")
    assert body.y == 300 and abs(body.x - 500) < 12


def test_plan_jump_refuses_the_impossible(world):
    assert plan_jump(Body(x=200, y=1040), 500, 100) is None       # far too high
    assert plan_jump(Body(x=200, y=1040), 1900, 1000) is None     # far too wide


def test_ceiling_stops_an_upward_throw(screen):
    world = World.build([screen])
    body = Body(x=500, y=300)
    body.launch(0, -3000)
    run(body, world, 0.3)
    assert body.y - body.height >= 0


@pytest.mark.parametrize("seed", range(6))
def test_soak_pet_never_escapes_and_stays_lively(seed):
    """Half an hour of simulated life on a changing two-monitor desktop."""
    rng = random.Random(seed)
    screens = [ScreenInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040)),
               ScreenInfo(Rect(1920, 200, 3200, 920), Rect(1920, 200, 3200, 880))]

    def random_windows():
        wins = []
        for i in range(rng.randint(0, 5)):
            x, y = rng.uniform(-200, 3000), rng.uniform(-50, 900)
            wins.append(WindowInfo(i + 1, Rect(x, y, x + rng.uniform(150, 900), y + rng.uniform(100, 700))))
        return wins

    world = World.build(screens, random_windows())
    body = Body()
    brain = Brain(body, MoodState(), BrainSettings(activity=1.0), rng)
    physics.respawn(body, world)
    seen, modes, dt = set(), set(), 1 / 30
    for i in range(30 * 60 * 30):
        if i % 600 == 0:                       # the user shuffles their windows every 20 s
            world = World.build(screens, random_windows())
        if i % 5000 == 2500:                   # ...and sometimes throws the pet
            brain.grab()
            body.x, body.y = rng.uniform(0, 3200), rng.uniform(200, 800)
            brain.release(rng.uniform(-2000, 2000), rng.uniform(-2000, 500))
        cursor = (rng.uniform(0, 3200), rng.uniform(0, 1080))
        brain.update(dt, world, cursor)
        brain.handle(step(body, world, dt), world)
        seen.add(brain.action)
        modes.add(body.mode)
        assert body.x == body.x and body.y == body.y            # no NaN
        assert -200 <= body.x <= 3400 and -200 <= body.y <= 1300, (i, body)
        if body.mode is Mode.GROUND:
            assert world.screen_at(body.x, body.y - 1) is not None, (i, body)
    assert {Action.WALK, Action.IDLE, Action.SIT, Action.FALL, Action.LAND} <= seen
    assert Mode.WALL in modes and Action.JUMP in seen
