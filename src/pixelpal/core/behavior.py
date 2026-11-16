"""Autonomous behaviour: decides what the pet does next and drives the physics body."""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum

from .mood import Mood, MoodState
from .physics import Body, Event, Mode, plan_jump, respawn
from .world import World


class Action(Enum):
    IDLE = "idle"
    LOOK = "look"
    WALK = "walk"
    RUN = "run"
    FOLLOW = "follow"
    SIT = "sit"
    SLEEP = "sleep"
    JUMP = "jump"
    FALL = "fall"
    LAND = "land"
    CLIMB = "climb"
    HANG = "hang"
    DRAGGED = "dragged"
    CELEBRATE = "celebrate"
    WAVE = "wave"
    DIZZY = "dizzy"
    PETTED = "petted"


RESTING = {Action.IDLE, Action.LOOK, Action.SIT, Action.SLEEP, Action.HANG}


@dataclass
class BrainSettings:
    activity: float = 0.6        # 0 = couch potato, 1 = zoomies
    follow_cursor: bool = True
    climbing: bool = True
    quiet: bool = False


class Brain:
    WALK, RUN, CLIMB_SPEED = 55.0, 150.0, 42.0

    def __init__(self, body: Body, mood: MoodState, settings: BrainSettings | None = None,
                 rng: random.Random | None = None) -> None:
        self.body = body
        self.mood = mood
        self.settings = settings or BrainSettings()
        self.rng = rng or random.Random()
        self.action = Action.FALL
        self.timer = 0.0
        self.direction = 1
        self.target_x: float | None = None
        self._jumping = False
        self._thrown = False
        self._want_grab = False
        self.cursor: tuple[float, float] | None = None

    # -- external nudges ------------------------------------------------------------------
    @property
    def asleep(self) -> bool:
        return self.action is Action.SLEEP

    def grab(self) -> None:
        self.body.mode, self.body.floor, self.body.wall = Mode.DRAGGED, None, None
        self.body.vx = self.body.vy = 0.0
        self._set(Action.DRAGGED, 0)
        self.mood.bump("dragged")

    def release(self, vx: float, vy: float) -> None:
        limit = 1400.0 * self.body.factor
        vx, vy = max(-limit, min(limit, vx)), max(-limit, min(limit, vy))
        self._thrown = (vx * vx + vy * vy) ** 0.5 > 700.0 * self.body.factor
        self._jumping = False
        self.body.launch(vx, vy)
        self._set(Action.FALL, 0)

    def pet(self) -> None:
        if self.body.mode is not Mode.GROUND:
            return
        if self.asleep:
            self.mood.bump("woke")
        self.mood.bump("petted")
        self._set(Action.PETTED, 1.2)

    def celebrate(self) -> None:
        self.mood.bump("task_done")
        self._interrupt(Action.CELEBRATE, 2.4)

    def alert(self) -> None:
        self.mood.bump("alert")
        self._interrupt(Action.WAVE, 1.6)

    def confuse(self) -> None:
        self.mood.bump("task_failed")
        self._interrupt(Action.DIZZY, 1.6)

    def sleep(self) -> None:
        self._interrupt(Action.SLEEP, 600.0)

    def wake(self) -> None:
        if self.asleep:
            self.mood.bump("woke")
            self._set(Action.LOOK, 1.0)

    def summon(self, world: World, x: float) -> None:
        """Drop in from the top of the screen above ``x``."""
        respawn(self.body, world, x)
        self._jumping = self._thrown = False
        self._set(Action.FALL, 0)

    def _interrupt(self, action: Action, duration: float) -> None:
        if self.body.mode is Mode.GROUND:
            self._set(action, duration)
        elif self.body.mode is Mode.WALL:
            self._set(Action.HANG, min(duration, 1.5))

    def _set(self, action: Action, duration: float) -> None:
        self.action, self.timer = action, duration
        self.target_x = None

    # -- main update: call before physics.step -------------------------------------------
    def update(self, dt: float, world: World, cursor: tuple[float, float] | None = None) -> None:
        self.cursor = cursor
        body = self.body
        moving = self.action in (Action.WALK, Action.RUN, Action.FOLLOW, Action.CLIMB, Action.JUMP)
        self.mood.update(dt, asleep=self.asleep, moving=moving)
        self.timer -= dt
        if body.mode is Mode.DRAGGED:
            self.action = Action.DRAGGED
        elif body.mode is Mode.AIR:
            self.action = Action.JUMP if self._jumping and body.vy < 0 else Action.FALL
        elif body.mode is Mode.WALL:
            self._update_wall(world)
        else:
            self._update_ground(world)

    def _update_ground(self, world: World) -> None:
        body, s = self.body, self.body.factor
        if self.action in (Action.FALL, Action.JUMP, Action.DRAGGED, Action.CLIMB, Action.HANG):
            self._set(Action.LAND, 0.25)
        if self.action is Action.SLEEP and self.mood.energy >= 0.98:
            self.timer = 0
        if self.action is Action.FOLLOW and self.cursor:
            dx = self.cursor[0] - body.x
            if abs(dx) < body.half_w * 1.5:
                self.mood.bump("followed")
                self._set(Action.LOOK, 1.5)
            else:
                self.direction = 1 if dx > 0 else -1
        if self.action in (Action.WALK, Action.RUN) and self.target_x is not None \
                and (self.target_x - body.x) * self.direction <= 0:
            self.timer = 0
        if self.timer <= 0:
            self._choose(world)
        if self.action is Action.WALK:
            body.vx = self.direction * self.WALK * s
        elif self.action in (Action.RUN, Action.FOLLOW):
            body.vx = self.direction * self.RUN * s
        elif body.mode is Mode.GROUND:
            body.vx = 0.0

    def _update_wall(self, world: World) -> None:
        body = self.body
        if self.action not in (Action.CLIMB, Action.HANG):
            self._set(Action.CLIMB, self.rng.uniform(3.0, 7.0))
        if self.timer <= 0:
            roll = self.rng.random()
            if self.action is Action.HANG:
                if roll < 0.65:
                    self._set(Action.CLIMB, self.rng.uniform(3.0, 7.0))
                else:
                    self._push_off()
                    return
            elif roll < 0.35:
                self._set(Action.HANG, self.rng.uniform(1.0, 3.5))
            elif roll < 0.85:
                self._set(Action.CLIMB, self.rng.uniform(3.0, 7.0))
            else:
                self._push_off()
                return
        body.vy = -self.CLIMB_SPEED * body.factor if self.action is Action.CLIMB else 0.0

    def _push_off(self) -> None:
        body = self.body
        side = body.wall.side if body.wall else -body.facing
        self._jumping = True
        body.launch(side * self.rng.uniform(120, 260) * body.factor, -self.rng.uniform(250, 420) * body.factor)
        self._set(Action.JUMP, 0)

    # -- choosing what to do next --------------------------------------------------------
    def _choose(self, world: World) -> None:
        rng, body, mood = self.rng, self.body, self.mood.current
        act = self.settings.activity * (0.5 if self.settings.quiet else 1.0)
        if mood is Mood.EXCITED:
            act = min(1.0, act + 0.3)
        sleepy = mood is Mood.SLEEPY
        cursor_far = bool(self.cursor) and abs(self.cursor[0] - body.x) > 150 * body.factor
        jump_target = self._pick_jump_target(world)
        weights = {
            Action.IDLE: 3.0,
            Action.LOOK: 1.5 + (1.5 if mood is Mood.CURIOUS else 0),
            Action.SIT: 1.5 + (1.5 if sleepy else 0),
            Action.SLEEP: 6.0 if sleepy else (0.15 if self.mood.energy < 0.6 else 0.0),
            Action.WALK: 5.0 * act * (0.4 if sleepy else 1.0),
            Action.RUN: 1.2 * act * (0.0 if sleepy else 1.0) * (2.0 if mood is Mood.EXCITED else 1.0),
            Action.JUMP: (1.4 * act if jump_target else 0.0) * (0.2 if sleepy else 1.0),
            Action.CELEBRATE: 0.5 if mood is Mood.EXCITED else 0.0,
            Action.WAVE: 0.25,
            Action.DIZZY: 1.5 if mood is Mood.CONFUSED else 0.0,
            Action.FOLLOW: (1.3 * act * (2.5 if mood is Mood.CURIOUS else 1.0)
                            if self.settings.follow_cursor and cursor_far and not sleepy else 0.0),
        }
        if self.action in RESTING or self.action is Action.LAND:
            weights[self.action] = weights.get(self.action, 0) * 0.3   # avoid repeating
        actions = list(weights)
        choice = rng.choices(actions, [weights[a] for a in actions])[0]

        if choice in (Action.WALK, Action.RUN):
            self._start_walk(choice)
        elif choice is Action.FOLLOW:
            self._set(Action.FOLLOW, rng.uniform(3, 7))
            body.avoid_edges = True
        elif choice is Action.JUMP and jump_target:
            self._jump_to(jump_target)
        elif choice is Action.SLEEP:
            self._set(Action.SLEEP, rng.uniform(40, 120))
        elif choice is Action.SIT:
            self._set(Action.SIT, rng.uniform(4, 12))
        elif choice is Action.IDLE:
            self._set(Action.IDLE, rng.uniform(2, 6))
        elif choice is Action.LOOK:
            self.mood.bump("looked")
            self._set(Action.LOOK, rng.uniform(1.5, 3))
        else:
            self._set(choice, {Action.CELEBRATE: 1.8, Action.WAVE: 1.6, Action.DIZZY: 1.6}.get(choice, 1.5))

    def _start_walk(self, action: Action) -> None:
        rng, body = self.rng, self.body
        floor = body.floor
        self._set(action, rng.uniform(2, 7) if action is Action.WALK else rng.uniform(1, 3))
        self.direction = rng.choice((-1, 1))
        if floor is not None:
            # Prefer the direction with more room.
            room_l, room_r = body.x - floor.x1, floor.x2 - body.x
            if rng.random() < 0.7:
                self.direction = 1 if room_r > room_l else -1
        # Window tops are fun to hop off; the screen floor ends in walls anyway.
        body.avoid_edges = not (floor is not None and floor.owner is not None and rng.random() < 0.35)
        self.mood.bump("explored")

    def _pick_jump_target(self, world: World) -> tuple[float, float, bool] | None:
        """A spot on another floor, or on the side of a window to grab: (x, y, grab)."""
        body = self.body
        options: list[tuple[float, float, bool]] = []
        if self.settings.climbing:
            for w in world.walls:
                outside = (body.x - w.x) * w.side
                if w.owner is None or outside < body.half_w * 2:
                    continue
                ty = w.y1 + body.height + 0.35 * max(0.0, w.y2 - w.y1 - body.height)
                if w.y2 - w.y1 > body.height * 1.5 and plan_jump(body, w.x - w.side * 3, ty) is not None:
                    options.append((w.x - w.side * 3, ty, True))
        for f in world.floors:
            if body.floor is not None and f.y == body.floor.y and f.owner == body.floor.owner:
                continue
            margin = min(body.half_w, (f.x2 - f.x1) / 2)
            for tx in (f.x1 + margin, (f.x1 + f.x2) / 2, f.x2 - margin):
                if abs(tx - body.x) < body.half_w and f.y < body.y:
                    continue  # straight up through our own floor is not a jump
                if plan_jump(body, tx, f.y) is not None:
                    options.append((tx, f.y, False))
        return self.rng.choice(options) if options else None

    def _jump_to(self, target: tuple[float, float, bool]) -> None:
        v = plan_jump(self.body, target[0], target[1])
        if v is None:
            return self._set(Action.IDLE, 1.0)
        self._jumping, self._want_grab = True, target[2]
        self.body.launch(*v)
        self._set(Action.JUMP, 0)

    def hop(self) -> None:
        if self.body.mode is Mode.GROUND:
            self._jumping = True
            self.body.launch(0.0, -330.0 * self.body.factor)
            self._set(Action.JUMP, 0)

    # -- reacting to physics: call after physics.step ------------------------------------
    def handle(self, events: list[Event], world: World) -> None:
        rng, body = self.rng, self.body
        for ev in events:
            if ev.kind == "landed":
                hard = self._thrown or ev.speed >= 1495 * body.factor
                self._jumping = self._thrown = self._want_grab = False
                if hard:
                    self.mood.bump("thrown")
                    self._set(Action.DIZZY, 1.8)
                else:
                    self._set(Action.LAND, 0.25)
            elif ev.kind == "hit_wall" and ev.wall is not None:
                if body.mode is Mode.AIR:
                    grab = self.settings.climbing and not self._thrown and (
                        self._want_grab or rng.random() < (0.5 if ev.wall.owner is None else 0.35))
                    if grab and ev.wall.y2 - ev.wall.y1 > body.height * 1.2:
                        body.attach_wall(ev.wall, world)
                        self._jumping = self._want_grab = False
                        self._set(Action.CLIMB, rng.uniform(1.5, 4))
                    elif ev.wall.owner is None:
                        body.vx = -body.vx * 0.35
                elif self.action is Action.FOLLOW:
                    self._set(Action.LOOK, 1.5)
                elif self.settings.climbing and not self.settings.quiet and rng.random() < 0.7 * (0.4 + self.settings.activity):
                    body.attach_wall(ev.wall, world)
                    self._set(Action.CLIMB, rng.uniform(2, 5))
                else:
                    self.direction = ev.wall.side
                    if rng.random() < 0.4:
                        self._set(Action.IDLE, rng.uniform(1, 3))
            elif ev.kind == "edge":
                if self.action is Action.FOLLOW or rng.random() < 0.5:
                    self._set(Action.LOOK, rng.uniform(1, 2.5))
                else:
                    self.direction = -self.direction
            elif ev.kind == "fell_off":
                self._jumping = False
                self._set(Action.FALL, 0)
            elif ev.kind == "lost_surface":
                self._jumping = False
                self.mood.bump("lost_surface")
                self._set(Action.FALL, 0)
            elif ev.kind == "wall_top":
                self._wall_top(ev, world)
            elif ev.kind == "wall_bottom":
                body.launch(0.0, 0.0)
                self._set(Action.FALL, 0)
            elif ev.kind == "respawn":
                self._jumping = self._thrown = False
                self._set(Action.FALL, 0)

    def _wall_top(self, ev: Event, world: World) -> None:
        body, wall = self.body, ev.wall
        assert wall is not None
        if wall.owner is not None:
            # Mantle onto the top of the window we just climbed.
            x = wall.x - wall.side * body.half_w
            floor = world.floor_at(x, wall.y1, wall.owner)
            if floor is not None:
                body.x = x
                body.attach_floor(floor, world)
                self._set(Action.LAND, 0.3)
                return
        if self.action is Action.CLIMB:
            self._set(Action.HANG, self.rng.uniform(0.8, 2.5))
