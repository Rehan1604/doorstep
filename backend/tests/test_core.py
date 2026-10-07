import json

import pytest
from fastapi.testclient import TestClient

from app import ai, config, main

GOOD = {"title": "Quiet Corner Hunt", "duration_minutes": 20, "difficulty": "easy",
        "objective": "Find one quiet spot and listen for two distinct sounds.",
        "steps": ["Walk slowly.", "Stop where it feels calm.", "Listen for 60 seconds."],
        "why_it_matters": "Listening resets attention.", "safety_notes": ["Stay on public paths."]}
REQ = {"minutes": 20, "energy": "low", "interest": "birds", "group": "solo"}


@pytest.fixture(autouse=True)
def tmpdb(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))


@pytest.fixture
def client():
    return TestClient(main.app)


def down(m, s):
    raise ai.ModelError("down")


def test_model_success(client, monkeypatch):
    monkeypatch.setattr(ai, "_chat", lambda m, s: json.dumps(GOOD))
    r = client.post("/api/missions", json=REQ).json()
    assert r["source"] == "model" and r["mission"]["title"] == "Quiet Corner Hunt"


def test_model_down_uses_fallback(client, monkeypatch):
    monkeypatch.setattr(ai, "_chat", down)
    r = client.post("/api/missions", json=REQ).json()
    assert r["source"] == "fallback" and r["mission"]["duration_minutes"] == 20


def test_malformed_json_retries_then_fallback(client, monkeypatch):
    calls = []
    monkeypatch.setattr(ai, "_chat", lambda m, s: calls.append(1) or "not json{")
    r = client.post("/api/missions", json=REQ).json()
    assert r["source"] == "fallback" and len(calls) == config.MAX_RETRIES + 1


def test_schema_violation_rejected(client, monkeypatch):
    monkeypatch.setattr(ai, "_chat", lambda m, s: json.dumps(dict(GOOD, steps=["only one"])))
    assert client.post("/api/missions", json=REQ).json()["source"] == "fallback"


def test_unsafe_content_rejected(client, monkeypatch):
    bad = dict(GOOD, steps=["Climb the fence.", "Walk on."])
    monkeypatch.setattr(ai, "_chat", lambda m, s: json.dumps(bad))
    assert client.post("/api/missions", json=REQ).json()["source"] == "fallback"


def test_input_validation(client):
    assert client.post("/api/missions", json={**REQ, "minutes": 3}).status_code == 422
    assert client.post("/api/missions", json={**REQ, "energy": "turbo"}).status_code == 422


def test_interest_is_sanitized(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(ai, "_chat", lambda m, s: seen.update(p=m[1]["content"]) or json.dumps(GOOD))
    client.post("/api/missions", json={**REQ, "interest": "birds {}\n[x]"})
    assert "{" not in seen["p"] and "[" not in seen["p"] and "\n" not in seen["p"]


def test_full_flow_and_history(client, monkeypatch):
    def fake(m, s):
        return json.dumps({"text": "You gave it 20 minutes and it showed."}) if "text" in s.get("properties", {}) else json.dumps(GOOD)
    monkeypatch.setattr(ai, "_chat", fake)
    mid = client.post("/api/missions", json=REQ).json()["id"]
    c = client.post(f"/api/missions/{mid}/complete", json={"completed": True, "surprise": "a heron"}).json()
    assert c["source"] == "model"
    h = client.get("/api/history").json()
    assert h["completed"] == 1 and h["minutes_outside"] == 20


def test_complete_unknown_mission_404(client):
    assert client.post("/api/missions/999/complete", json={"completed": True}).status_code == 404


def test_reflection_fallback(client, monkeypatch):
    monkeypatch.setattr(ai, "_chat", down)
    mid = client.post("/api/missions", json=REQ).json()["id"]
    c = client.post(f"/api/missions/{mid}/complete", json={"completed": True}).json()
    assert c["source"] == "fallback" and "20 minutes" in c["reflection"]


def test_transcribe_ok(client, monkeypatch):
    from app import voice
    monkeypatch.setattr(voice, "transcribe", lambda d: "a heron on the wall")
    assert client.post("/api/transcribe", content=b"abc").json() == {"text": "a heron on the wall"}


def test_transcribe_unavailable_and_limits(client, monkeypatch):
    from app import voice

    def nope(d): raise voice.VoiceUnavailable()
    monkeypatch.setattr(voice, "transcribe", nope)
    assert client.post("/api/transcribe", content=b"abc").status_code == 503
    assert client.post("/api/transcribe", content=b"").status_code == 400
    assert client.post("/api/transcribe", content=b"x" * (voice.MAX_BYTES + 1)).status_code == 413


def test_transcribe_garbage_audio(client, monkeypatch):
    from app import voice

    def bad(d): raise RuntimeError("decode")
    monkeypatch.setattr(voice, "transcribe", bad)
    assert client.post("/api/transcribe", content=b"abc").status_code == 422
