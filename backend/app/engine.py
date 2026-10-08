"""Orchestration: bandit picks the style, the LLM writes it, embeddings keep it fresh and personal."""
from . import ai, store
from .ml import bandit, embed
from .schema import Completion, Mission, MissionRequest


def _text(m: Mission) -> str:
    return f"{m.title}. {m.objective}. {' '.join(m.steps)}"


def _score(m: Mission, client: str) -> tuple[list[float], str, float, str | None]:
    """Embed a mission and find its closest past mission: (vec, embedder, best_similarity, closest_title)."""
    vec, emb = embed.embed(_text(m))
    best, closest = 0.0, None
    for title, v in store.past_vectors(client, emb):
        s = embed.cosine(vec, v)
        if s > best:
            best, closest = s, title
    return vec, emb, best, closest


def create(req: MissionRequest, client: str) -> dict:
    stats = store.arm_stats(client)
    style, info = bandit.choose(req.energy, req.group, req.minutes, stats)
    titles = store.recent_titles(client=client)
    mission, source = ai.generate_mission(req, titles, style=style)
    vec, emb, best, closest = _score(mission, client)

    # Semantic novelty guard: one retry if it is nearly the same as a recent mission.
    if source == "model" and closest and best > embed.novelty_limit(emb):
        m2, s2 = ai.generate_mission(req, titles, style=style, differ_from=closest)
        if s2 == "model":
            v2, e2, b2, c2 = _score(m2, client)
            if e2 != emb or b2 < best:
                mission, vec, emb, best, closest = m2, v2, e2, b2, c2

    novelty = round(1 - best, 2) if closest else None
    mid = store.save_mission(req.model_dump(), mission.model_dump(), source, client, style,
                             bandit.bucket(req.energy, req.group), novelty, emb, vec)
    return {"id": mid, "source": source, "mission": mission, "style": style, "style_label": info["label"],
            "why": bandit.explain(info), "novelty": novelty}


def finish(mid: int, body: Completion, client: str) -> dict | None:
    row = store.get_mission(mid)
    if not row or row["client"] != client:
        return None
    first_time = row["completed"] is None

    memories: list[str] = []
    note_vec = note_emb = None
    if body.surprise.strip():
        note_vec, note_emb = embed.embed(body.surprise)
        ranked = sorted(((embed.cosine(note_vec, v), t) for t, v in store.past_notes(client, note_emb, mid)),
                        reverse=True)
        memories = [t for s, t in ranked[:2] if s >= embed.recall_min(note_emb)]

    text, source = ai.generate_reflection(Mission(**row["mission"]), body.completed, body.surprise, memories)
    store.complete(mid, body.completed, body.surprise, body.feeling, text, note_vec, note_emb)
    if first_time and row.get("style") and row.get("bucket"):
        store.apply_reward(client, row["bucket"], row["style"], bandit.reward(body.completed, body.feeling),
                           bandit.GOOD_AT)
    return {"reflection": text, "source": source, "recalled": len(memories)}


def insights(client: str) -> dict:
    rows = store.insights(client)
    for r in rows:
        r["label"] = bandit.STYLES[r["style"]][0]
    rows.sort(key=lambda r: r["mean"], reverse=True)
    return {"styles": rows, "total": sum(r["n"] for r in rows),
            "best": rows[0]["label"] if rows and rows[0]["n"] >= 2 else None}