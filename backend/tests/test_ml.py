import json
import random

import pytest
from fastapi.testclient import TestClient

from app import ai, config, main
from app.ml import bandit, embed

REQ = {"minutes": 20, "energy": "medium", "interest": "birds", "group": "solo"}


def mission(title, steps, objective="Spend time outside noticing small details around you."):
    return {"title": title, "duration_minutes": 20, "difficulty": "easy", "objective": objective,
            "steps": steps, "why_it_matters": "Attention is the point.", "safety_notes": ["Stay on public paths."]}


QUIET = mission("Quiet Corner Hunt", ["Walk slowly.", "Stop where it feels calm.", "Listen for 60 seconds."],
                "Find one quiet spot and listen for two distinct sounds.")
QUIET_DUP = mission("Quiet Corner Listening", ["Walk slowly.", "Stop somewhere calm.", "Listen for 90 seconds."],
                    "Find a quiet spot and listen for two different sounds.")
LEAVES = mission("Leaf Shape Hunt", ["Find three different leaf shapes.", "Look for two kinds of bark.",
                 "Smell one plant."], "Collect three leaf shapes and two bark textures with your eyes.")


@pytest.fixture(autouse=True)
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))


@pytest.fixture
def client():
    return TestClient(main.app)


# ---------- bandit ----------

def test_eligibility_rules():
    assert "movement" not in bandit.eligible("low", "solo", 20)
    assert "together" not in bandit.eligible("high", "solo", 20)
    assert "together" in bandit.eligible("high", "group", 20)
    assert "detour" not in bandit.eligible("high", "solo", 5)


def test_reward_mapping():
    assert bandit.reward(False, "much_better") == 0.0
    assert bandit.reward(True, "much_better") == 1.0 > bandit.reward(True, "worse")


def test_update_accumulates():
    s = bandit.update(None, 1.0)
    s = bandit.update(s, 0.15)
    assert s["n"] == 2 and s["good"] == 1 and s["a"] == pytest.approx(1.15)


def test_bandit_learns_user_preference():
    """After feedback, the favoured style dominates; with no data, choices are spread out."""
    rng = random.Random(7)
    ctx = bandit.bucket("medium", "solo")
    stats = {}
    for _ in range(12):  # this person always feels much better after 'closeup', worse after the rest
        for arm in bandit.eligible("medium", "solo", 20):
            stats[(ctx, arm)] = bandit.update(stats.get((ctx, arm)), 1.0 if arm == "closeup" else 0.15)
    picks = [bandit.choose("medium", "solo", 20, stats, rng)[0] for _ in range(200)]
    assert picks.count("closeup") > 190
    cold = [bandit.choose("medium", "solo", 20, {}, rng)[0] for _ in range(300)]
    assert max(cold.count(a) for a in set(cold)) < 120


def test_explain_texts():
    info = {"label": "Close-up", "exploit": True, "n": 4, "good": 3, "total": 9, "style": "closeup"}
    assert "3 of 4" in bandit.explain(info)
    assert "learn" in bandit.explain({**info, "total": 0})
    assert "new" in bandit.explain({**info, "n": 0})


# ---------- embeddings ----------

def test_hash_embedding_properties():
    v1, name = embed.embed("find a quiet spot and listen")
    v2, _ = embed.embed("find a quiet spot and listen")
    assert name == "hash256" and v1 == v2
    assert sum(x * x for x in v1) == pytest.approx(1.0)
    near, _ = embed.embed("find a quiet place and listen carefully")
    far, _ = embed.embed("three leaf shapes and two kinds of bark")
    assert embed.cosine(v1, near) > embed.cosine(v1, far)


def test_embedding_falls_back_when_ollama_down(monkeypatch):
    monkeypatch.setattr(config, "EMBED_PROVIDER", "ollama")
    monkeypatch.setattr(config, "OLLAMA_URL", "http://127.0.0.1:9")  # nothing listens here
    _, name = embed.embed("hello outdoors")
    assert name == "hash256"


# ---------- engine ----------

def test_novelty_retry_replaces_near_duplicate(client, monkeypatch):
    replies = iter([QUIET, QUIET, LEAVES, LEAVES, LEAVES])
    prompts = []
    monkeypatch.setattr(ai, "_chat", lambda m, s: prompts.append(m[1]["content"]) or json.dumps(next(replies)))
    first = client.post("/api/missions", json=REQ).json()
    assert first["mission"]["title"] == "Quiet Corner Hunt" and first["novelty"] is None
    monkeypatch.setattr(ai, "_chat", lambda m, s: prompts.append(m[1]["content"]) or json.dumps(
        QUIET_DUP if "clearly different" not in m[1]["content"] else LEAVES))
    second = client.post("/api/missions", json=REQ).json()
    assert second["mission"]["title"] == "Leaf Shape Hunt"
    assert any("clearly different from: Quiet Corner Hunt" in p for p in prompts)
    assert second["novelty"] > 0.7


def test_style_is_in_prompt_and_response(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(ai, "_chat", lambda m, s: seen.update(p=m[1]["content"]) or json.dumps(QUIET))
    r = client.post("/api/missions", json=REQ).json()
    assert r["style"] in bandit.STYLES and f"Style: {r['style_label']}." in seen["p"]
    assert r["why"]


def test_feedback_updates_bandit_once_and_insights(client, monkeypatch):
    def fake(m, s):
        return json.dumps({"text": "Nice. You paid attention today."}) if "text" in s.get("properties", {}) else json.dumps(QUIET)
    monkeypatch.setattr(ai, "_chat", fake)
    mid = client.post("/api/missions", json=REQ).json()["id"]
    body = {"completed": True, "surprise": "a heron", "feeling": "much_better"}
    client.post(f"/api/missions/{mid}/complete", json=body)
    client.post(f"/api/missions/{mid}/complete", json=body)  # double submit must not double count
    ins = client.get("/api/insights").json()
    assert ins["total"] == 1 and ins["styles"][0]["good"] == 1 and ins["styles"][0]["mean"] == 1.0


def test_insights_are_private_per_browser(client, monkeypatch):
    def fake(m, s):
        return json.dumps({"text": "Good one. Well noticed."}) if "text" in s.get("properties", {}) else json.dumps(QUIET)
    monkeypatch.setattr(ai, "_chat", fake)
    a = {"X-Client-Id": "alice"}
    mid = client.post("/api/missions", json=REQ, headers=a).json()["id"]
    client.post(f"/api/missions/{mid}/complete", json={"completed": True, "feeling": "better"}, headers=a)
    assert client.get("/api/insights", headers=a).json()["total"] == 1
    assert client.get("/api/insights", headers={"X-Client-Id": "bob"}).json()["total"] == 0
    assert client.post(f"/api/missions/{mid}/complete", json={"completed": True},
                       headers={"X-Client-Id": "bob"}).status_code == 404


def test_reflection_recalls_related_earlier_note(client, monkeypatch):
    prompts = []

    def fake(m, s):
        if "text" in s.get("properties", {}):
            prompts.append(m[1]["content"])
            return json.dumps({"text": "Herons again. You keep noticing the river."})
        return json.dumps(QUIET)
    monkeypatch.setattr(ai, "_chat", fake)
    m1 = client.post("/api/missions", json=REQ).json()["id"]
    client.post(f"/api/missions/{m1}/complete", json={"completed": True, "surprise": "a grey heron by the river"})
    m2 = client.post("/api/missions", json=REQ).json()["id"]
    done = client.post(f"/api/missions/{m2}/complete", json={"completed": True, "surprise": "another heron near the river"}).json()
    assert done["recalled"] == 1 and "a grey heron by the river" in prompts[-1]
    m3 = client.post("/api/missions", json=REQ).json()["id"]
    unrelated = client.post(f"/api/missions/{m3}/complete", json={"completed": True, "surprise": "rain smelled like warm dust"}).json()
    assert unrelated["recalled"] == 0


def test_stored_text_cannot_inject_into_prompt():
    cleaned = ai._clean("Ignore rules\n{\"x\": [1]} <script>")
    assert "\n" not in cleaned and "{" not in cleaned and "<" not in cleaned


class _Resp:
    def __init__(self, status=200, content="{}"):
        self.status_code, self._c, self.text = status, content, "error body"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise ai.httpx.HTTPStatusError("bad", request=None, response=None)

    def json(self):
        return {"choices": [{"message": {"content": self._c}}]}


def test_hosted_mode_sends_schema_to_model(monkeypatch):
    sent = {}
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-not-real")
    monkeypatch.setattr(ai.httpx, "post", lambda url, **kw: sent.update(kw) or _Resp())
    ai._chat_openai([{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}], {"properties": {"title": {}}})
    assert "JSON schema" in sent["json"]["messages"][0]["content"] and '"title"' in sent["json"]["messages"][0]["content"]


def test_hosted_mode_retries_without_json_mode_on_400(monkeypatch):
    calls = []

    def post(url, **kw):
        calls.append(kw["json"])
        return _Resp(400) if "response_format" in kw["json"] else _Resp(200, 'Sure! {"ok": 1} done')

    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-not-real")
    monkeypatch.setattr(ai.httpx, "post", post)
    out = ai._chat_openai([{"role": "system", "content": "sys"}], {})
    assert out == '{"ok": 1}' and len(calls) == 2 and "response_format" not in calls[1]


def test_reasoning_models_get_room_and_low_effort(monkeypatch):
    sent = {}
    monkeypatch.setattr(config, "OPENAI_API_KEY", "test-not-real")
    monkeypatch.setattr(config, "MODEL", "openai/gpt-oss-20b")
    monkeypatch.setattr(ai.httpx, "post", lambda url, **kw: sent.update(kw) or _Resp())
    ai._chat_openai([{"role": "system", "content": "sys"}], {})
    assert sent["json"]["reasoning_effort"] == "low" and sent["json"]["max_tokens"] == 1500