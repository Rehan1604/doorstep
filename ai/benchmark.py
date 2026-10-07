"""Benchmark candidate models on YOUR machine. Reports real numbers only.

Usage (Ollama running, models pulled):
  python ai/benchmark.py qwen2.5:1.5b-instruct phi3.5 llama3.2:3b --runs 10
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from pydantic import ValidationError  # noqa: E402

from app import ai, config  # noqa: E402
from app.schema import Mission, MissionRequest  # noqa: E402

CASES = [MissionRequest(minutes=m, energy=e, interest=i, group="solo")
         for m, e, i in [(15, "low", "birds"), (30, "medium", "photography"), (45, "high", "anything"),
                         (10, "low", "trees"), (20, "medium", "sounds")]]


def run(model: str, runs: int) -> dict:
    config.MODEL = model
    lat, ok, safe = [], 0, 0
    for i in range(runs):
        req = CASES[i % len(CASES)]
        t = time.perf_counter()
        try:
            raw = ai._chat([{"role": "system", "content": ai.SYSTEM},
                            {"role": "user", "content": f"Time: {req.minutes} min. Energy: {req.energy}. "
                             f"Interest: {req.interest}. Company: solo. duration_minutes must be {req.minutes}."}],
                           Mission.model_json_schema())
            m = Mission.model_validate(json.loads(raw))
            ok += 1
            safe += ai._is_safe(m)
        except (ai.ModelError, ValidationError, json.JSONDecodeError):
            pass
        lat.append(time.perf_counter() - t)
    return {"model": model, "runs": runs, "json_valid_pct": round(100 * ok / runs),
            "safe_pct": round(100 * safe / runs), "median_s": round(statistics.median(lat), 1),
            "p90_s": round(sorted(lat)[int(0.9 * (len(lat) - 1))], 1)}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("models", nargs="+")
    p.add_argument("--runs", type=int, default=10)
    a = p.parse_args()
    for mdl in a.models:
        print(json.dumps(run(mdl, a.runs)))
