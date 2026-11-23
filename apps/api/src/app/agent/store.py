"""Owner-scoped conversation history in a local SQLite file (ignored by Git)."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time

MAX_TURNS = 100


class ConversationStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as con:
            con.execute("""CREATE TABLE IF NOT EXISTS conversation (id TEXT PRIMARY KEY, owner TEXT NOT NULL,
                           created REAL NOT NULL, updated REAL NOT NULL, turns TEXT NOT NULL)""")
            con.commit()

    def connect(self):
        return sqlite3.connect(self.path)

    def get(self, conversation_id: str, owner: str) -> list[dict] | None:
        with closing(self.connect()) as con:
            row = con.execute("SELECT turns FROM conversation WHERE id=? AND owner=?", (conversation_id, owner)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, conversation_id: str, owner: str, turns: list[dict]) -> None:
        now = time.time()
        with closing(self.connect()) as con:
            con.execute("""INSERT INTO conversation VALUES (?,?,?,?,?)
                           ON CONFLICT(id) DO UPDATE SET turns=excluded.turns, updated=excluded.updated
                           WHERE conversation.owner=excluded.owner""",
                        (conversation_id, owner, now, now, json.dumps(turns, ensure_ascii=False)))
            con.commit()

    def list(self, owner: str, limit: int = 30) -> list[dict]:
        with closing(self.connect()) as con:
            rows = con.execute("SELECT id, updated, turns FROM conversation WHERE owner=? ORDER BY updated DESC LIMIT ?",
                               (owner, limit)).fetchall()
        return [{"conversation_id": cid, "updated": updated, "title": (json.loads(turns) or [{}])[0].get("question", "")[:80],
                 "turns": len(json.loads(turns))} for cid, updated, turns in rows]
