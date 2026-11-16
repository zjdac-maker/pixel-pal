"""What the pet says, when it says it, and the little rewards it earns."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .mood import Mood

PHRASES: dict[str, list[str]] = {
    "hello": ["Hi! I live here now.", "Reporting for duty!", "Oh! A desktop. Nice."],
    "petted": ["Hehe!", "Again, again!", "That tickles!", "Aww."],
    "thrown": ["Wheee... oof.", "I can see my house from here!", "Was that necessary?"],
    "woke": ["Mm? I'm up, I'm up.", "Five more minutes..."],
    "task_done": ["Done! High five!", "Nailed it!", "Ta-da!", "Another one in the bag!"],
    "task_failed": ["Uh oh. That didn't work.", "Hmm. Something went wrong."],
    "timer_done": ["Ding! Time's up!", "Time! You made it!"],
    "pomodoro_done": ["Focus session done. Stretch time!", "Pure focus. Proud of you!"],
    "break_done": ["Break's over. Ready when you are!", "Back to it? I believe in you."],
    "low_battery": ["Psst... battery's at {value}%. Feed the laptop!", "Running low: {value}% left!"],
    "high_cpu": ["Phew, it's warm in here. CPU at {value}%!", "Something's working hard: CPU {value}%."],
    "unlock": ["Ooh, I earned a {value}! Look at me!", "New accessory: a {value}!"],
    "lost_surface": ["Hey! I was standing on that!", "Where'd the floor go?"],
    Mood.HAPPY.value: ["Nice day on the desktop.", "La la la...", "You're doing great.", "I like it here."],
    Mood.SLEEPY.value: ["*yaaawn*", "So... sleepy...", "Nap time soon?"],
    Mood.CURIOUS.value: ["What are you working on?", "Ooh, what does this window do?", "Where's the pointer going?"],
    Mood.EXCITED.value: ["Woo!", "Let's gooo!", "Best. Day. Ever."],
    Mood.CONFUSED.value: ["Which way is up again?", "Huh?", "I meant to do that."],
}


def phrase(category: str, rng: random.Random, value: object = "") -> str:
    return rng.choice(PHRASES[category]).format(value=value)


class Chatter:
    """Decides when the pet makes an unprompted remark."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self.rng = rng or random.Random()
        self._wait = 0.0
        self.reset(0.5)

    def reset(self, chattiness: float) -> None:
        # chattiness 1.0 -> a remark every 1-3 min; 0.1 -> every 10-30 min
        base = 90.0 / max(chattiness, 0.05)
        self._wait = self.rng.uniform(base * 0.7, base * 2.0)

    def update(self, dt: float, mood: Mood, chattiness: float, quiet: bool, asleep: bool) -> str | None:
        if quiet or chattiness <= 0 or asleep:
            return None
        self._wait -= dt
        if self._wait > 0:
            return None
        self.reset(chattiness)
        return phrase(mood.value, self.rng)


@dataclass(frozen=True)
class Reward:
    accessory: str
    label: str
    tasks_needed: int


REWARDS = [
    Reward("bow", "bow", 1),
    Reward("scarf", "cosy scarf", 3),
    Reward("glasses", "pair of cool shades", 6),
    Reward("party_hat", "party hat", 10),
    Reward("crown", "tiny crown", 20),
]


def unlocked(tasks_done: int) -> list[Reward]:
    return [r for r in REWARDS if tasks_done >= r.tasks_needed]


def newly_unlocked(before: int, after: int) -> list[Reward]:
    return [r for r in REWARDS if before < r.tasks_needed <= after]
