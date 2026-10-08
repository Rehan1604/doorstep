"""Does the style bandit actually learn? Synthetic-user simulation (NOT real user data).

Two kinds of simulated people, 500 of each, 20 missions each, noisy feedback, 10% skipped missions:
  trait   - one favourite style that works across every context
  context - a different favourite style in each energy/group context
We compare the bandit with random style choice over the LAST 10 missions.

Usage: python ai/simulate_bandit.py
"""
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.ml import bandit  # noqa: E402

USERS, MISSIONS = 500, 20
CONTEXTS = [("low", "solo"), ("medium", "solo"), ("high", "solo"), ("medium", "group")]
SHARED_STYLES = ["stillness", "hunt", "closeup"]  # eligible in every context above


def feeling(rng, is_fav):
    if rng.random() < 0.1:
        return False, "same"
    pool = (["much_better"] * 5 + ["better"] * 3 + ["same"] * 2) if is_fav else (["worse"] * 3 + ["same"] * 5 + ["better"] * 2)
    return True, rng.choice(pool)


def run(kind, policy, seed):
    rng = random.Random(seed)
    trait = rng.choice(SHARED_STYLES)
    fav = {c: trait if kind == "trait" else rng.choice(bandit.eligible(c[0], c[1], 20)) for c in CONTEXTS}
    stats, hits, rewards = {}, [], []
    for i in range(MISSIONS):
        energy, group = CONTEXTS[i % len(CONTEXTS)]
        arm = (bandit.choose(energy, group, 20, stats, rng)[0] if policy == "bandit"
               else rng.choice(bandit.eligible(energy, group, 20)))
        done, feel = feeling(rng, arm == fav[(energy, group)])
        r = bandit.reward(done, feel)
        key = (bandit.bucket(energy, group), arm)
        stats[key] = bandit.update(stats.get(key), r)
        hits.append(arm == fav[(energy, group)])
        rewards.append(r)
    return statistics.mean(hits[-10:]), statistics.mean(rewards[-10:])


if __name__ == "__main__":
    for kind in ("trait", "context"):
        print(f"[{kind} users]")
        for policy in ("random", "bandit"):
            res = [run(kind, policy, s) for s in range(USERS)]
            print(f"  {policy:7s} picks favourite style: {100 * statistics.mean(h for h, _ in res):3.0f}%"
                  f" | avg reward: {statistics.mean(r for _, r in res):.2f}")