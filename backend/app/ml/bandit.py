"""Contextual Thompson-sampling bandit: learns which mission STYLE works for this person.

Arm = mission style. Context = energy x group. Reward = how they felt afterwards.
Each (context, arm) keeps a Beta posterior; other contexts share most of their evidence
so a new context does not start from zero. Pure Python, no dependencies, runs offline.
"""
import random

STYLES = {
    "stillness": ("Stillness", "Mostly stand or sit still and notice. Very little walking."),
    "movement": ("Steady walk", "A steady walk with one simple noticing task."),
    "hunt": ("Sensory hunt", "Find specific things by sight, sound, smell or touch, like a short checklist."),
    "closeup": ("Close-up", "Study the details of one small thing for several minutes."),
    "together": ("Together", "A small shared outdoor game or question for the group."),
    "detour": ("Detour", "Take one unfamiliar turn on a public path and notice what is new."),
}
REWARD = {"worse": 0.15, "same": 0.4, "better": 0.75, "much_better": 1.0}
GOOD_AT = 0.75        # reward at or above this counts as "felt better"
GLOBAL_WEIGHT = 0.8   # weight of evidence from other contexts (tuned in ai/simulate_bandit.py)


def reward(completed: bool, feeling: str) -> float:
    return REWARD.get(feeling, 0.5) if completed else 0.0


def bucket(energy: str, group: str) -> str:
    return f"{energy}|{group}"


def eligible(energy: str, group: str, minutes: int) -> list[str]:
    arms = list(STYLES)
    if energy == "low":
        arms.remove("movement")
    if group == "solo":
        arms.remove("together")
    if minutes < 10:
        arms.remove("detour")
    return arms


def update(stat: dict | None, r: float) -> dict:
    s = dict(stat or {"a": 0.0, "b": 0.0, "n": 0, "good": 0})
    s["a"] += r
    s["b"] += 1.0 - r
    s["n"] += 1
    s["good"] += int(r >= GOOD_AT)
    return s


def _global(stats: dict, arm: str) -> dict:
    out = {"a": 0.0, "b": 0.0, "n": 0, "good": 0}
    for (_, a), s in stats.items():
        if a == arm:
            for k in out:
                out[k] += s[k]
    return out


def _posterior(stats: dict, ctx: str, arm: str) -> tuple[float, float, dict]:
    own = stats.get((ctx, arm), {"a": 0.0, "b": 0.0, "n": 0, "good": 0})
    glob = _global(stats, arm)
    alpha = 1.0 + own["a"] + GLOBAL_WEIGHT * (glob["a"] - own["a"])
    beta = 1.0 + own["b"] + GLOBAL_WEIGHT * (glob["b"] - own["b"])
    return alpha, beta, glob


def choose(energy: str, group: str, minutes: int, stats: dict, rng: random.Random | None = None) -> tuple[str, dict]:
    rng = rng or random
    ctx = bucket(energy, group)
    arms = eligible(energy, group, minutes)
    post = {a: _posterior(stats, ctx, a) for a in arms}
    pick = max(arms, key=lambda a: rng.betavariate(post[a][0], post[a][1]))
    best = max(arms, key=lambda a: post[a][0] / (post[a][0] + post[a][1]))
    glob = post[pick][2]
    total = sum(s["n"] for s in stats.values())
    return pick, {"style": pick, "label": STYLES[pick][0], "exploit": pick == best,
                  "n": glob["n"], "good": glob["good"], "total": total}


def explain(info: dict) -> str:
    label = info["label"].lower()
    if info["total"] == 0:
        return "First mission: trying a style at random so I can learn what works for you."
    if info["n"] == 0:
        return f"Trying something new: you haven't done a {label} mission yet."
    if info["exploit"]:
        return f"{info['label']} has left you feeling better in {info['good']} of {info['n']} missions."
    return f"Testing {label} again ({info['n']} so far) to check it isn't a better fit than it looks."