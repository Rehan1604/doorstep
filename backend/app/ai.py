"""Local model access via Ollama. All inference stays on this machine."""
import json
import logging
import re

import httpx
from pydantic import ValidationError

from . import config
from .fallback import fallback_mission, fallback_reflection
from .schema import Mission, MissionRequest, Reflection

log = logging.getLogger("doorstep.ai")

SYSTEM = (
    "You design tiny outdoor missions. Output JSON only. Concrete, sensory, safe. "
    "Never suggest climbing, private property, wildlife contact, roads, night isolation, or bad weather. "
    "Steps must fit the time. Under 6 steps."
)
# Substring screen on model output: a cheap second safety layer after the prompt.
UNSAFE = re.compile(
    r"\b(climb|trespass|private property|approach (the )?(animal|wildlife)|touch (the )?(animal|wildlife)|"
    r"swim|cliff|highway|traffic lane|alone at night|after dark)\b",
    re.I,
)


class ModelError(Exception):
    pass


def _chat(messages: list[dict], schema: dict) -> str:
    """Single Ollama call. Raises ModelError on any transport problem."""
    try:
        r = httpx.post(
            f"{config.OLLAMA_URL}/api/chat",
            json={"model": config.MODEL, "messages": messages, "stream": False,
                  "format": schema, "keep_alive": "30m", "options": {"temperature": 0.4, "num_predict": 400}},
            timeout=config.TIMEOUT_S,
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise ModelError(str(e)) from e


def model_status() -> dict:
    try:
        r = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2)
        names = [m["name"] for m in r.json().get("models", [])]
        return {"ollama": True, "model": config.MODEL, "model_present": config.MODEL in names}
    except (httpx.HTTPError, ValueError, KeyError):
        return {"ollama": False, "model": config.MODEL, "model_present": False}


def _is_safe(m: Mission) -> bool:
    text = " ".join([m.title, m.objective, *m.steps])
    return not UNSAFE.search(text)


def generate_mission(req: MissionRequest, recent_titles: list[str]) -> tuple[Mission, str]:
    """Returns (mission, source) where source is 'model' or 'fallback'."""
    user = (f"Time: {req.minutes} min. Energy: {req.energy}. Interest: {req.interest}. "
            f"Company: {req.group}. Avoid repeating: {', '.join(recent_titles[:3]) or 'none'}. "
            f"duration_minutes must be {req.minutes}.")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            raw = _chat(msgs, Mission.model_json_schema())
            m = Mission.model_validate(json.loads(raw))
            if not _is_safe(m):
                log.warning("unsafe content rejected (attempt %d)", attempt)
                continue
            return m.model_copy(update={"duration_minutes": req.minutes}), "model"
        except ModelError as e:
            log.warning("model unavailable: %s", e)
            break  # no point retrying a dead server
        except (ValidationError, json.JSONDecodeError) as e:
            log.warning("bad model output (attempt %d): %s", attempt, e)
    return fallback_mission(req), "fallback"


def generate_reflection(mission: Mission, completed: bool, surprise: str) -> tuple[str, str]:
    prompt = (f"Mission: {mission.title}. Completed: {completed}. Surprise: {surprise[:200] or 'none'}. "
              "Write 1-2 warm, plain sentences. No hashtags, no emojis, no cliches. Output JSON {\"text\": ...}.")
    msgs = [{"role": "system", "content": "You write short honest reflections."},
            {"role": "user", "content": prompt}]
    try:
        raw = _chat(msgs, Reflection.model_json_schema())
        return Reflection.model_validate(json.loads(raw)).text, "model"
    except (ModelError, ValidationError, json.JSONDecodeError):
        return fallback_reflection(completed, mission.duration_minutes), "fallback"


def warmup() -> None:
    """Load the model into RAM at startup so the first mission isn't the slow one."""
    try:
        httpx.post(f"{config.OLLAMA_URL}/api/generate",
                   json={"model": config.MODEL, "prompt": "", "keep_alive": "30m"}, timeout=120)
    except httpx.HTTPError:
        log.info("warmup skipped: model server not reachable")
