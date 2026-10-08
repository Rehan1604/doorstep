"""Local SQLite storage. In local mode nothing here ever leaves the machine."""
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """CREATE TABLE IF NOT EXISTS missions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, request TEXT, mission TEXT, source TEXT,
 completed INTEGER, surprise TEXT, feeling TEXT, reflection TEXT)"""
ARMS = """CREATE TABLE IF NOT EXISTS arm_stats(
 client TEXT, bucket TEXT, arm TEXT, a REAL, b REAL, n INTEGER, good INTEGER,
 PRIMARY KEY(client, bucket, arm))"""
# Columns added after v0.1; applied to existing databases on connect.
MIGRATIONS = {"client": "TEXT DEFAULT ''", "style": "TEXT", "bucket": "TEXT", "novelty": "REAL",
              "embedder": "TEXT", "vec": "TEXT", "note_vec": "TEXT", "note_embedder": "TEXT"}
HIDDEN = ("vec", "note_vec")


@contextmanager
def db():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute(SCHEMA)
    con.execute(ARMS)
    have = {r["name"] for r in con.execute("PRAGMA table_info(missions)")}
    for col, typ in MIGRATIONS.items():
        if col not in have:
            con.execute(f"ALTER TABLE missions ADD COLUMN {col} {typ}")
    try:
        yield con
        con.commit()
    finally:
        con.close()


def save_mission(request: dict, mission: dict, source: str, client: str = "", style: str | None = None,
                 bucket: str | None = None, novelty: float | None = None, embedder: str | None = None,
                 vec: list[float] | None = None) -> int:
    with db() as c:
        cur = c.execute(
            "INSERT INTO missions(created,request,mission,source,client,style,bucket,novelty,embedder,vec)"
            " VALUES(?,?,?,?,?,?,?,?,?,?)",
            (time.time(), json.dumps(request), json.dumps(mission), source, client, style, bucket, novelty,
             embedder, json.dumps([round(x, 4) for x in vec]) if vec else None))
        return cur.lastrowid


def get_mission(mid: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
    return _row(row) if row else None


def complete(mid: int, completed: bool, surprise: str, feeling: str, reflection: str,
             note_vec: list[float] | None = None, note_embedder: str | None = None) -> None:
    with db() as c:
        c.execute("UPDATE missions SET completed=?,surprise=?,feeling=?,reflection=?,note_vec=?,note_embedder=?"
                  " WHERE id=?",
                  (int(completed), surprise, feeling, reflection,
                   json.dumps([round(x, 4) for x in note_vec]) if note_vec else None, note_embedder, mid))


def recent_titles(n: int = 3, client: str = "") -> list[str]:
    with db() as c:
        rows = c.execute("SELECT mission FROM missions WHERE client=? ORDER BY id DESC LIMIT ?",
                         (client, n)).fetchall()
    return [json.loads(r["mission"])["title"] for r in rows]


def past_vectors(client: str, embedder: str, n: int = 20) -> list[tuple[str, list[float]]]:
    """(title, vector) of this client's recent missions made with the same embedder."""
    with db() as c:
        rows = c.execute("SELECT mission, vec FROM missions WHERE client=? AND embedder=? AND vec IS NOT NULL"
                         " ORDER BY id DESC LIMIT ?", (client, embedder, n)).fetchall()
    return [(json.loads(r["mission"])["title"], json.loads(r["vec"])) for r in rows]


def past_notes(client: str, embedder: str, exclude_id: int, n: int = 50) -> list[tuple[str, list[float]]]:
    with db() as c:
        rows = c.execute("SELECT surprise, note_vec FROM missions WHERE client=? AND note_embedder=?"
                         " AND note_vec IS NOT NULL AND id!=? ORDER BY id DESC LIMIT ?",
                         (client, embedder, exclude_id, n)).fetchall()
    return [(r["surprise"], json.loads(r["note_vec"])) for r in rows]


def arm_stats(client: str) -> dict:
    with db() as c:
        rows = c.execute("SELECT bucket,arm,a,b,n,good FROM arm_stats WHERE client=?", (client,)).fetchall()
    return {(r["bucket"], r["arm"]): {k: r[k] for k in ("a", "b", "n", "good")} for r in rows}


def apply_reward(client: str, bucket: str, arm: str, r: float, good_at: float) -> None:
    with db() as c:
        c.execute(
            "INSERT INTO arm_stats(client,bucket,arm,a,b,n,good) VALUES(?,?,?,?,?,1,?)"
            " ON CONFLICT(client,bucket,arm) DO UPDATE SET a=a+excluded.a, b=b+excluded.b,"
            " n=n+1, good=good+excluded.good",
            (client, bucket, arm, r, 1.0 - r, int(r >= good_at)))


def insights(client: str) -> list[dict]:
    with db() as c:
        rows = c.execute("SELECT arm, SUM(a) a, SUM(n) n, SUM(good) good FROM arm_stats WHERE client=?"
                         " GROUP BY arm", (client,)).fetchall()
    return [{"style": r["arm"], "n": r["n"], "good": r["good"], "mean": round(r["a"] / r["n"], 2)}
            for r in rows if r["n"]]


def history(client: str = "") -> dict:
    with db() as c:
        rows = c.execute("SELECT * FROM missions WHERE completed=1 AND client=? ORDER BY id DESC LIMIT 50",
                         (client,)).fetchall()
    items = [_row(r) for r in rows]
    minutes = sum(i["mission"]["duration_minutes"] for i in items)
    return {"completed": len(items), "minutes_outside": minutes, "items": items}


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["request"] = json.loads(d["request"])
    d["mission"] = json.loads(d["mission"])
    d["vec_json"], d["note_vec_json"] = d.pop("vec", None), d.pop("note_vec", None)
    return d