import random

from pixelpal.core import physics
from pixelpal.core.animation import Animator
from pixelpal.core.behavior import Action, Brain, BrainSettings
from pixelpal.core.mood import Mood, MoodState
from pixelpal.core.personality import REWARDS, Chatter, newly_unlocked, unlocked
from pixelpal.core.physics import Body, Mode, step
from pixelpal.core.world import World

DT = 1 / 30


def make(world, seed=0, **settings):
    body = Body()
    brain = Brain(body, MoodState(), BrainSettings(**settings), random.Random(seed))
    physics.respawn(body, world, 700)
    return body, brain


def live(body, brain, world, seconds, cursor=None):
    seen = []
    for _ in range(int(seconds / DT)):
        brain.update(DT, world, cursor)
        brain.handle(step(body, world, DT), world)
        if not seen or seen[-1] is not brain.action:
            seen.append(brain.action)
    return seen


def test_drops_in_lands_then_does_things_on_its_own(world):
    body, brain = make(world)
    seen = live(body, brain, world, 120)
    assert seen[:2] == [Action.FALL, Action.LAND]
    assert len(set(seen)) >= 5


def test_drag_and_gentle_drop(world):
    body, brain = make(world)
    live(body, brain, world, 3)
    brain.grab()
    assert body.mode is Mode.DRAGGED
    body.x, body.y = 1500, 400
    assert live(body, brain, world, 1) == [Action.DRAGGED]
    assert (body.x, body.y) == (1500, 400)          # physics leaves a held pet alone
    brain.release(0, 0)
    seen = live(body, brain, world, 3)
    assert seen[0] is Action.FALL and Action.LAND in seen and body.y == 1040


def test_hard_throw_makes_it_dizzy_and_confused(world):
    body, brain = make(world)
    live(body, brain, world, 3)
    brain.grab()
    body.x, body.y = 1500, 500
    brain.release(900, -900)
    seen = live(body, brain, world, 4)
    assert Action.DIZZY in seen
    assert brain.mood.confusion > 0.3


def test_petting_wakes_and_cheers(world):
    body, brain = make(world)
    live(body, brain, world, 3)
    brain.sleep()
    assert brain.asleep
    joy = brain.mood.joy
    brain.pet()
    assert brain.action is Action.PETTED and brain.mood.joy > joy


def test_sleep_restores_energy_and_ends(world):
    body, brain = make(world)
    live(body, brain, world, 3)
    brain.mood.energy = 0.1
    assert brain.mood.current is Mood.SLEEPY
    brain.sleep()
    live(body, brain, world, 100)
    assert brain.mood.energy > 0.9 and not brain.asleep


def test_celebrate_and_summon(world):
    body, brain = make(world)
    live(body, brain, world, 3)
    brain.celebrate()
    assert brain.action is Action.CELEBRATE and brain.mood.current is Mood.EXCITED
    brain.summon(world, 1800)
    live(body, brain, world, 3)
    assert abs(body.x - 1800) < 200 and body.mode is Mode.GROUND


def test_quiet_low_activity_pet_mostly_rests(world):
    body, brain = make(world, seed=3, activity=0.0, quiet=True)
    live(body, brain, world, 3)
    x = body.x
    seen = set(live(body, brain, world, 120))
    assert not seen & {Action.WALK, Action.RUN, Action.JUMP, Action.FOLLOW}
    assert body.x == x


def test_follows_the_cursor_when_curious(world):
    reached = 0
    for seed in range(8):
        body, brain = make(world, seed=seed, activity=1.0)
        live(body, brain, world, 2)
        brain.mood.curiosity = 1.0
        if Action.FOLLOW in live(body, brain, world, 40, cursor=(1500, 1000)):
            reached += 1
    assert reached >= 5


def test_no_climbing_when_disabled(screen):
    world = World.build([screen])
    body, brain = make(world, seed=1, activity=1.0, climbing=False)
    seen = set(live(body, brain, world, 600))
    assert Action.CLIMB not in seen and Action.WALK in seen


def test_mood_decays_back_to_happy():
    mood = MoodState()
    mood.bump("thrown")
    assert mood.current is Mood.CONFUSED
    mood.update(30)
    assert mood.current is Mood.HAPPY
    mood.bump("task_done")
    assert mood.current is Mood.EXCITED


def test_animator_loops_and_switches():
    anim = Animator({"a": [("a0", 100), ("a1", 100)], "b": [("b0", 50)]})
    assert anim.frame == "a0" and not anim.update(0.05)
    assert anim.update(0.06) and anim.frame == "a1"
    assert anim.update(0.1) and anim.frame == "a0"
    anim.play("b")
    assert anim.frame == "b0"
    anim.play("missing")
    assert anim.name == "b"


def test_chatter_respects_quiet_and_sleep():
    chatter = Chatter(random.Random(1))
    assert all(chatter.update(60, Mood.HAPPY, 1.0, True, False) is None for _ in range(50))
    assert all(chatter.update(60, Mood.HAPPY, 1.0, False, True) is None for _ in range(50))
    assert all(chatter.update(60, Mood.HAPPY, 0.0, False, False) is None for _ in range(50))
    lines = [chatter.update(30, Mood.SLEEPY, 1.0, False, False) for _ in range(40)]
    spoken = [line for line in lines if line]
    assert 3 <= len(spoken) <= 20            # talks, but not constantly


def test_rewards_unlock_in_order():
    assert unlocked(0) == []
    assert [r.accessory for r in newly_unlocked(0, 1)] == ["bow"]
    assert newly_unlocked(1, 2) == []
    assert len(unlocked(1000)) == len(REWARDS)
