"""SQLite-backed session persistence — Phase 6 replacement for JSON file sessions.

Database: data/sessions.db
Tables:
  sessions     — one row per session (metadata + intent + saved flag)
  interactions — one row per interaction, FK to sessions

Drop-in replacement: exposes the same public API as SessionManager so
webapp.py and orchestrator.py need zero changes.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Generator, List

# Default: project_root/data (two levels above src/services/)
_DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_DDL = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    saved         INTEGER NOT NULL DEFAULT 0,
    saved_at      TEXT,
    intent        TEXT,
    last_sections TEXT
);
CREATE TABLE IF NOT EXISTS interactions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL REFERENCES sessions(session_id),
    data        TEXT NOT NULL,
    timestamp   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions(session_id);
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SQLiteSessionManager:
    """SQLite-backed session manager — same public API as SessionManager."""

    def __init__(self, storage_dir: str | None = None) -> None:
        self._dir = storage_dir or str(_DEFAULT_DATA_DIR)
        os.makedirs(self._dir, exist_ok=True)
        self._db_path = os.path.join(self._dir, "sessions.db")
        self._init_db()

    # ── DB helpers ─────────────────────────────────────────────────────────

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(_DDL)

    @contextmanager
    def _conn(self) -> Generator[sqlite3.Connection, None, None]:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    # ── Public API ─────────────────────────────────────────────────────────

    def start_session(self, user_id: str) -> str:
        session_id = f"{user_id}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, user_id, created_at) VALUES (?,?,?)",
                (session_id, user_id, _now()),
            )
        return session_id

    def log_interaction(self, session_id: str, interaction: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO interactions (session_id, data, timestamp) VALUES (?,?,?)",
                (session_id, json.dumps(interaction, default=str), _now()),
            )

    # ── Intent ─────────────────────────────────────────────────────────────

    def save_intent(self, session_id: str, intent: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE sessions SET intent=? WHERE session_id=?",
                (json.dumps(intent, default=str), session_id),
            )

    def get_intent(self, session_id: str) -> Dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT intent FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        if row and row["intent"]:
            return json.loads(row["intent"])
        return None

    # ── Save / pin ─────────────────────────────────────────────────────────

    def save_briefing(self, session_id: str, sections: Dict[str, Any]) -> bool:
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE sessions SET saved=1, saved_at=?, last_sections=? WHERE session_id=?",
                    (_now(), json.dumps(sections, default=str), session_id),
                )
            return True
        except Exception:
            return False

    def is_saved(self, session_id: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT saved FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
        return bool(row and row["saved"])

    # ── Full session read ───────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if not row:
                return None
            interactions = [
                {**json.loads(r["data"]), "timestamp": r["timestamp"]}
                for r in conn.execute(
                    "SELECT data, timestamp FROM interactions WHERE session_id=? ORDER BY id",
                    (session_id,),
                ).fetchall()
            ]
        return {
            "session_id":    row["session_id"],
            "user_id":       row["user_id"],
            "created_at":    row["created_at"],
            "saved":         bool(row["saved"]),
            "saved_at":      row["saved_at"],
            "intent":        json.loads(row["intent"]) if row["intent"] else None,
            "last_sections": json.loads(row["last_sections"]) if row["last_sections"] else None,
            "interactions":  interactions,
        }

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
            summaries = []
            for row in rows:
                intent = json.loads(row["intent"]) if row["intent"] else {}
                first_q_rows = conn.execute(
                    "SELECT data FROM interactions WHERE session_id=? ORDER BY id LIMIT 10",
                    (row["session_id"],),
                ).fetchall()
                query = ""
                for r in first_q_rows:
                    d = json.loads(r["data"])
                    if d.get("query"):
                        query = d["query"]
                        break
                summaries.append({
                    "session_id": row["session_id"],
                    "user_id":    row["user_id"],
                    "created_at": row["created_at"],
                    "saved":      bool(row["saved"]),
                    "query":      query,
                    "location":   intent.get("location", ""),
                    "sections":   intent.get("sections", []),
                })
        return summaries

    def delete_session(self, session_id: str) -> bool:
        """Delete a single session and its associated interactions."""
        try:
            with self._conn() as conn:
                conn.execute("DELETE FROM interactions WHERE session_id=?", (session_id,))
                cur = conn.execute("DELETE FROM sessions WHERE session_id=?", (session_id,))
                return cur.rowcount > 0
        except Exception:
            return False

    def clear_history(self) -> bool:
        """Clear all sessions and interactions from the database."""
        try:
            with self._conn() as conn:
                conn.execute("DELETE FROM interactions")
                conn.execute("DELETE FROM sessions")
                return True
        except Exception:
            return False
