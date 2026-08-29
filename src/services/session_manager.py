"""Session persistence layer.

On-disk format (sessions/{session_id}.json):
{
  "session_id":   "guest-20260809180809",
  "user_id":      "guest",
  "created_at":   "2026-08-09T18:08:09.297101",
  "saved":        false,
  "intent":       { ... } | null,       ← persisted after first briefing
  "last_sections":{ ... } | null,       ← full section payloads, written on save
  "interactions": [ { ...,"timestamp":} ]
}
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

# Default: project_root/data/sessions (three levels above src/services/)
_DEFAULT_SESSION_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "sessions"


class SessionManager:
    def __init__(self, storage_dir: str | None = None) -> None:
        self.storage_dir = storage_dir or str(_DEFAULT_SESSION_DIR)
        os.makedirs(self.storage_dir, exist_ok=True)

    # ------------------------------------------------------------------ public

    def start_session(self, user_id: str) -> str:
        session_id = f"{user_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        payload: Dict[str, Any] = {
            "session_id": session_id,
            "user_id": user_id,
            "created_at": datetime.utcnow().isoformat(),
            "saved": False,
            "intent": None,
            "last_sections": None,
            "interactions": [],
        }
        self._write(session_id, payload)
        return session_id

    def log_interaction(self, session_id: str, interaction: Dict[str, Any]) -> None:
        payload = self._read(session_id)
        payload.setdefault("interactions", []).append(
            {**interaction, "timestamp": datetime.utcnow().isoformat()}
        )
        self._write(session_id, payload)

    # ---- intent persistence (Phase 3) ------------------------------------

    def save_intent(self, session_id: str, intent: Dict[str, Any]) -> None:
        """Write the parsed intent into the session file so it survives restarts."""
        payload = self._read(session_id)
        payload["intent"] = intent
        self._write(session_id, payload)

    def get_intent(self, session_id: str) -> Dict[str, Any] | None:
        """Return the stored intent for a session, or None if not present."""
        return self._read(session_id).get("intent")

    # ---- save/pin briefing (Phase 3) -------------------------------------

    def save_briefing(self, session_id: str, sections: Dict[str, Any]) -> bool:
        """Mark a session as saved and persist the full section payloads."""
        try:
            payload = self._read(session_id)
            payload["saved"] = True
            payload["last_sections"] = sections
            payload["saved_at"] = datetime.utcnow().isoformat()
            self._write(session_id, payload)
            return True
        except Exception:
            return False

    def is_saved(self, session_id: str) -> bool:
        return bool(self._read(session_id).get("saved", False))

    # ---- full session read (Phase 3) -------------------------------------

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        """Return the full session dict, or None if the file does not exist."""
        path = os.path.join(self.storage_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        return self._read(session_id)

    def list_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return summary dicts for the most-recent sessions, newest first."""
        summaries: List[Dict[str, Any]] = []
        sessions_path = self.storage_dir
        try:
            files = sorted(
                (f for f in os.listdir(sessions_path) if f.endswith(".json")),
                reverse=True,
            )[:limit]
        except FileNotFoundError:
            return []

        for fname in files:
            try:
                data = self._read(fname[:-5])  # strip .json
                # Pull the first query out of interactions[]
                interactions = data.get("interactions", [])
                first_query = ""
                for ia in interactions:
                    if ia.get("query"):
                        first_query = ia["query"]
                        break
                summaries.append(
                    {
                        "session_id": data.get("session_id", fname[:-5]),
                        "user_id": data.get("user_id", "guest"),
                        "created_at": data.get("created_at", ""),
                        "saved": data.get("saved", False),
                        "query": first_query,
                        "location": (data.get("intent") or {}).get("location", ""),
                        "sections": (data.get("intent") or {}).get("sections", []),
                    }
                )
            except Exception:
                pass
        return summaries

    def delete_session(self, session_id: str) -> bool:
        """Delete a single session json file."""
        try:
            path = os.path.join(self.storage_dir, f"{session_id}.json")
            if os.path.exists(path):
                os.remove(path)
                return True
            return False
        except Exception:
            return False

    def clear_history(self) -> bool:
        """Clear all session files in storage directory."""
        try:
            for fname in os.listdir(self.storage_dir):
                if fname.endswith(".json"):
                    os.remove(os.path.join(self.storage_dir, fname))
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------ private

    def _write(self, session_id: str, payload: Dict[str, Any]) -> None:
        path = os.path.join(self.storage_dir, f"{session_id}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, default=str)

    def _read(self, session_id: str) -> Dict[str, Any]:
        path = os.path.join(self.storage_dir, f"{session_id}.json")
        if not os.path.exists(path):
            return {"session_id": session_id, "interactions": []}
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
