from pixelpal.core.geometry import Rect, subtract_intervals
from pixelpal.core.world import ScreenInfo, WindowInfo, World


def test_subtract_intervals():
    assert subtract_intervals((0, 10), [(3, 5)]) == [(0, 3), (5, 10)]
    assert subtract_intervals((0, 10), [(-5, 20)]) == []
    assert subtract_intervals((0, 10), [(0, 2), (8, 12)]) == [(2, 8)]
    assert subtract_intervals((0, 10), [(1, 9)], min_len=2) == []


def test_screen_gives_floor_and_two_walls(screen):
    w = World.build([screen])
    assert [(f.y, f.x1, f.x2) for f in w.floors] == [(1040, 0, 1920)]   # top of the taskbar
    assert sorted((x.x, x.side) for x in w.walls) == [(0, 1), (1920, -1)]


def test_window_top_is_a_floor_and_sides_are_walls(world):
    tops = [f for f in world.floors if f.owner == 1]
    assert [(f.y, f.x1, f.x2) for f in tops] == [(300, 400, 1000)]
    sides = sorted((x.x, x.side) for x in world.walls if x.owner == 1)
    assert sides == [(400, -1), (1000, 1)]


def test_covered_part_of_a_window_top_is_not_walkable(screen):
    front = WindowInfo(2, Rect(600, 200, 800, 500), "front")    # hides the middle of the top edge
    back = WindowInfo(1, Rect(400, 300, 1000, 700), "back")
    w = World.build([screen], [front, back])
    assert [(f.x1, f.x2) for f in w.floors if f.owner == 1] == [(400, 600), (800, 1000)]
    assert [(f.x1, f.x2) for f in w.floors if f.owner == 2] == [(600, 800)]


def test_maximised_window_adds_nothing(screen):
    w = World.build([screen], [WindowInfo(1, Rect(0, 0, 1920, 1040), "max")])
    assert all(f.owner is None for f in w.floors)
    assert all(x.owner is None for x in w.walls)


def test_window_hanging_off_screen_is_clipped(screen):
    w = World.build([screen], [WindowInfo(1, Rect(1700, 400, 2300, 800), "half off")])
    assert [(f.x1, f.x2) for f in w.floors if f.owner == 1] == [(1700, 1920)]
    assert [x.x for x in w.walls if x.owner == 1] == [1700]


def test_shared_edge_between_monitors_is_not_a_wall():
    a = ScreenInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))
    b = ScreenInfo(Rect(1920, 0, 3840, 1080), Rect(1920, 0, 3840, 1040))
    w = World.build([a, b])
    assert sorted(x.x for x in w.walls) == [0, 3840]


def test_shorter_neighbour_leaves_a_partial_wall():
    a = ScreenInfo(Rect(0, 0, 1920, 1080), Rect(0, 0, 1920, 1040))
    b = ScreenInfo(Rect(1920, 0, 3200, 720), Rect(1920, 0, 3200, 680))
    w = World.build([a, b])
    inner = [x for x in w.walls if x.x == 1920]
    assert [(x.y1, x.y2, x.side) for x in inner] == [(680, 1040, -1)]


def test_fullscreen_detection(screen):
    video = WindowInfo(1, Rect(0, 0, 1920, 1080), "video")
    assert World.build([screen], [video]).fullscreen_on(500, 500)
    assert not World.build([screen], [WindowInfo(1, Rect(0, 0, 1920, 1040), "max")]).fullscreen_on(500, 500)
    small_on_top = WindowInfo(2, Rect(400, 400, 700, 700), "popup")
    assert not World.build([screen], [small_on_top, video]).fullscreen_on(500, 500)
