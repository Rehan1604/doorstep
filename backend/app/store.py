"""Local SQLite storage. Nothing here ever leaves the machine."""
import json
import sqlite3
import time
from contextlib import contextmanager

from . import config

SCHEMA = """CREATE TABLE IF NOT EXISTS missions(
 id INTEGER PRIMARY KEY AUTOINCREMENT, created REAL, request TEXT, mission TEXT, source TEXT,
 completed INTEGER, surprise TEXT, feeling TEXT, reflection TEXT)"""


@contextmanager
def db():
    con = sqlite3.connect(config.DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute(SCHEMA)
    try:
        yield con
        con.commit()
    finally:
        con.close()


def save_mission(request: dict, mission: dict, source: str) -> int:
    with db() as c:
        cur = c.execute("INSERT INTO missions(created,request,mission,source) VALUES(?,?,?,?)",
                        (time.time(), json.dumps(request), json.dumps(mission), source))
        return cur.lastrowid


def get_mission(mid: int) -> dict | None:
    with db() as c:
        row = c.execute("SELECT * FROM missions WHERE id=?", (mid,)).fetchone()
    return _row(row) if row else None


def complete(mid: int, completed: bool, surprise: str, feeling: str, reflection: str) -> None:
    with db() as c:
        c.execute("UPDATE missions SET completed=?,surprise=?,feeling=?,reflection=? WHERE id=?",
                  (int(completed), surprise, feeling, reflection, mid))


def recent_titles(n: int = 3) -> list[str]:
    with db() as c:
        rows = c.execute("SELECT mission FROM missions ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [json.loads(r["mission"])["title"] for r in rows]


def history() -> dict:
    with db() as c:
        rows = c.execute("SELECT * FROM missions WHERE completed=1 ORDER BY id DESC LIMIT 50").fetchall()
    items = [_row(r) for r in rows]
    minutes = sum(i["mission"]["duration_minutes"] for i in items)
    return {"completed": len(items), "minutes_outside": minutes, "items": items}


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["request"] = json.loads(d["request"])
    d["mission"] = json.loads(d["mission"])
    return d
