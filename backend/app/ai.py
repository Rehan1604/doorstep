"""LLM access for Doorstep.

AI_PROVIDER=ollama -> local open-weight model via Ollama (default, fully local)
AI_PROVIDER=openai -> any OpenAI-compatible API (e.g. Groq) for the hosted demo
"""
import json
import logging
import re

import httpx
from pydantic import ValidationError

from . import config
from .fallback import fallback_mission, fallback_reflection
from .ml.bandit import STYLES
from .schema import Mission, MissionRequest, Reflection

log = logging.getLogger("doorstep.ai")

SYSTEM = (
    "You design tiny outdoor missions. Output JSON only. Concrete, sensory, safe. "
    "Never suggest climbing, private property, wildlife contact, roads, night isolation, or bad weather. "
    "Steps must fit the time. Under 6 steps."
)
UNSAFE = re.compile(
    r"\b(climb|trespass|private property|approach (the )?(animal|wildlife)|touch (the )?(animal|wildlife)|"
    r"swim|cliff|highway|traffic lane|alone at night|after dark)\b", re.I)


class ModelError(Exception):
    pass


def _clean(text: str, limit: int = 80) -> str:
    """Strip anything that could break out of a one-line prompt (stored text is untrusted)."""
    return re.sub(r"[^A-Za-z0-9 ,.'-]", "", text)[:limit].strip()


def _chat_ollama(messages: list[dict], schema: dict) -> str:
    try:
        r = httpx.post(f"{config.OLLAMA_URL}/api/chat",
                       json={"model": config.MODEL, "messages": messages, "stream": False, "format": schema,
                             "keep_alive": "30m", "options": {"temperature": 0.4, "num_predict": 400}},
                       timeout=config.TIMEOUT_S)
        r.raise_for_status()
        return r.json()["message"]["content"]
    except (httpx.HTTPError, KeyError, ValueError) as e:
        raise ModelError(str(e)) from e


def _extract_json(text: str) -> str:
    """Models sometimes wrap JSON in prose or code fences; keep the outermost object."""
    i, j = text.find("{"), text.rfind("}")
    return text[i:j + 1] if 0 <= i < j else text


def _chat_openai(messages: list[dict], schema: dict) -> str:
    if not config.OPENAI_API_KEY:
        raise ModelError("OPENAI_API_KEY is missing")
    # json_object mode does not enforce a schema, so the field names must be in the prompt.
    msgs = [dict(m) for m in messages]
    msgs[0]["content"] += " Reply with one JSON object matching this JSON schema: " + json.dumps(schema)
    body = {"model": config.MODEL, "messages": msgs, "temperature": 0.4, "max_tokens": 600}
    if "gpt-oss" in config.MODEL:
        # Reasoning models spend output tokens thinking: keep it short and leave room for the answer.
        body["reasoning_effort"] = "low"
        body["max_tokens"] = 1500
    url = f"{config.OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}", "Content-Type": "application/json"}
    for json_mode in (True, False):  # some hosted models reject JSON mode: retry once without it
        payload = dict(body, response_format={"type": "json_object"}) if json_mode else body
        try:
            r = httpx.post(url, headers=headers, json=payload, timeout=config.TIMEOUT_S)
            if r.status_code >= 400:
                log.warning("hosted model returned %s (json_mode=%s): %s", r.status_code, json_mode, r.text[:300])
                if r.status_code == 400 and json_mode:
                    continue
            r.raise_for_status()
            return _extract_json(r.json()["choices"][0]["message"]["content"])
        except (httpx.HTTPError, KeyError, ValueError) as e:
            raise ModelError(str(e)) from e
    raise ModelError("hosted model rejected the request")

def _chat(messages: list[dict], schema: dict) -> str:
    provider = config.AI_PROVIDER.lower()
    if provider == "ollama":
        return _chat_ollama(messages, schema)
    if provider == "openai":
        return _chat_openai(messages, schema)
    raise ModelError(f"Unknown AI_PROVIDER: {config.AI_PROVIDER}")


def model_status() -> dict:
    if config.AI_PROVIDER.lower() == "ollama":
        try:
            r = httpx.get(f"{config.OLLAMA_URL}/api/tags", timeout=2)
            names = [m["name"] for m in r.json().get("models", [])]
            return {"provider": "ollama", "ollama": True, "model": config.MODEL, "model_present": config.MODEL in names}
        except (httpx.HTTPError, ValueError, KeyError):
            return {"provider": "ollama", "ollama": False, "model": config.MODEL, "model_present": False}
    return {"provider": config.AI_PROVIDER, "model": config.MODEL, "configured": bool(config.OPENAI_API_KEY)}


def _is_safe(m: Mission) -> bool:
    return not UNSAFE.search(" ".join([m.title, m.objective, *m.steps]))


def generate_mission(req: MissionRequest, recent_titles: list[str], style: str | None = None,
                     differ_from: str | None = None) -> tuple[Mission, str]:
    """Returns (mission, source); source is 'model' or 'fallback'."""
    parts = [f"Time: {req.minutes} min.", f"Energy: {req.energy}.", f"Interest: {req.interest}.",
             f"Company: {req.group}."]
    if style in STYLES:
        parts.append(f"Style: {STYLES[style][0]}. {STYLES[style][1]}")
    avoid = [_clean(t) for t in recent_titles[:3]]
    if differ_from:
        avoid.insert(0, _clean(differ_from))
        parts.append(f"It must be clearly different from: {_clean(differ_from)}.")
    parts.append(f"Avoid repeating: {', '.join(avoid) or 'none'}.")
    parts.append(f"duration_minutes must be {req.minutes}.")
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": " ".join(parts)}]
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            m = Mission.model_validate(json.loads(_chat(msgs, Mission.model_json_schema())))
            if not _is_safe(m):
                log.warning("unsafe content rejected (attempt %d)", attempt)
                continue
            return m.model_copy(update={"duration_minutes": req.minutes}), "model"
        except ModelError as e:
            log.warning("model unavailable: %s", e)
            break
        except (ValidationError, json.JSONDecodeError) as e:
            log.warning("bad model output (attempt %d): %s", attempt, e)
    return fallback_mission(req, style), "fallback"


def generate_reflection(mission: Mission, completed: bool, surprise: str,
                        memories: list[str] | None = None) -> tuple[str, str]:
    mem = ""
    if memories:
        mem = ("Earlier notes from them: " + " | ".join(_clean(m, 120) for m in memories[:2]) +
               ". If one clearly connects to today, weave it into one clause; otherwise ignore it. ")
    prompt = (f"Mission: {_clean(mission.title)}. Completed: {completed}. Surprise: {_clean(surprise, 200) or 'none'}. "
              f"{mem}Write 1-2 warm, plain sentences. No hashtags, no emojis, no cliches. "
              'Output JSON {"text": "..."}.')
    msgs = [{"role": "system", "content": "You write short honest reflections."},
            {"role": "user", "content": prompt}]
    try:
        return Reflection.model_validate(json.loads(_chat(msgs, Reflection.model_json_schema()))).text, "model"
    except (ModelError, ValidationError, json.JSONDecodeError):
        return fallback_reflection(completed, mission.duration_minutes), "fallback"


def warmup() -> None:
    if config.AI_PROVIDER.lower() != "ollama":
        return
    try:
        httpx.post(f"{config.OLLAMA_URL}/api/generate",
                   json={"model": config.MODEL, "prompt": "", "keep_alive": "30m"}, timeout=120)
    except httpx.HTTPError:
        log.info("warmup skipped: model server not reachable")