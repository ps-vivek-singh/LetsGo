"""Commute Commander web server.

Run with:  python scripts/webapp.py
Visit:     http://localhost:8000

Endpoints
---------
GET  /api/history                              list past sessions (newest 20)
GET  /api/history/{session_id}                 full session detail
GET  /api/briefing/{session_id}/{section}      poll one section
GET  /api/briefing/{session_id}/stream         SSE stream — one event per agent
POST /api/briefing                             run full briefing, returns structured JSON
POST /api/briefing/{session_id}/{section}/refresh   re-run one agent
POST /api/briefing/{session_id}/save           pin/save a briefing to disk
POST /api/briefing/{session_id}/rerun          re-run all agents with current intent
PATCH /api/briefing/{session_id}/intent        update intent fields, optionally re-run
GET  /api/settings                             load user settings
PUT  /api/settings                             save user settings
"""

from __future__ import annotations

import json
import queue
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ── Resolve project root and add src/ to import path ────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR      = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from agents.orchestrator import OrchestratorAgent
from services.db import SQLiteSessionManager
from services.settings_manager import SettingsManager
from services.telemetry import telemetry


ROOT             = PROJECT_ROOT
STATIC_DIRECTORY = ROOT / "frontend"
DATA_DIR         = ROOT / "data"

session_manager  = SQLiteSessionManager(storage_dir=str(DATA_DIR))
orchestrator     = OrchestratorAgent(session_manager=session_manager)
settings_manager = SettingsManager(storage_dir=str(ROOT / "config"))

# ── URL patterns ────────────────────────────────────────────────────────────
_SECTION_RE = r"(?P<section>weather|news|commute|breakfast|itinerary)"
_SID_RE     = r"(?P<session_id>[^/]+)"

_RE_BRIEFING        = re.compile(r"^/api/briefing$")
_RE_SECTION_POLL    = re.compile(rf"^/api/briefing/{_SID_RE}/{_SECTION_RE}$")
_RE_SECTION_REFRESH = re.compile(rf"^/api/briefing/{_SID_RE}/{_SECTION_RE}/refresh$")
_RE_SAVE            = re.compile(rf"^/api/briefing/{_SID_RE}/save$")
_RE_RERUN           = re.compile(rf"^/api/briefing/{_SID_RE}/rerun$")
_RE_INTENT          = re.compile(rf"^/api/briefing/{_SID_RE}/intent$")
_RE_STREAM          = re.compile(rf"^/api/briefing/{_SID_RE}/stream$")
_RE_HISTORY_DETAIL  = re.compile(rf"^/api/history/{_SID_RE}$")
_RE_SETTINGS        = re.compile(r"^/api/settings$")
_RE_COMMUTE         = re.compile(r"^/api/commute$")
_RE_ITINERARY       = re.compile(r"^/api/itinerary$")
_RE_SHARE_EMAIL     = re.compile(r"^/api/share/email$")
_RE_OBS_METRICS     = re.compile(r"^/api/observability/metrics$")
_RE_OBS_TRACES      = re.compile(r"^/api/observability/traces$")



def _get_intent(session_id: str) -> dict:
    """Return intent from disk (survives restarts). Falls back to empty dict."""
    return session_manager.get_intent(session_id) or {}


class CommuteCommanderHandler(SimpleHTTPRequestHandler):
    """Serves static UI files and the structured JSON API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC_DIRECTORY), **kwargs)

    def handle_one_request(self) -> None:
        self._req_t0 = time.perf_counter()
        super().handle_one_request()

    def log_request(self, code='-', size='-') -> None:
        try:
            status_int = int(code) if str(code).isdigit() else 200
        except Exception:
            status_int = 200
        duration_ms = (time.perf_counter() - getattr(self, "_req_t0", time.perf_counter())) * 1000
        telemetry.http(
            method=self.command,
            path=self.path,
            status=status_int,
            duration_ms=duration_ms,
            ip=self.client_address[0] if self.client_address else "127.0.0.1",
        )

    def log_error(self, fmt: str, *args) -> None:
        telemetry.error("HTTP", fmt % args)

    # ── GET ─────────────────────────────────────────────────────────────────
    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/api/history":
            self._handle_history_list()
            return

        if _RE_SETTINGS.match(path):
            self._handle_settings_get()
            return

        if _RE_OBS_METRICS.match(path):
            self._handle_observability_metrics()
            return

        if _RE_OBS_TRACES.match(path):
            self._handle_observability_traces()
            return

        m = _RE_HISTORY_DETAIL.match(path)
        if m:
            self._handle_history_detail(m.group("session_id"))
            return

        m = _RE_STREAM.match(path)
        if m:
            self._handle_stream(m.group("session_id"))
            return

        m = _RE_SECTION_POLL.match(path)
        if m:
            self._handle_section_poll(m.group("session_id"), m.group("section"))
            return

        super().do_GET()

    # ── POST ─────────────────────────────────────────────────────────────────
    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if _RE_BRIEFING.match(path):
            self._handle_briefing()
            return

        if _RE_COMMUTE.match(path):
            self._handle_commute_direct()
            return

        if _RE_ITINERARY.match(path):
            self._handle_itinerary_direct()
            return

        m = _RE_SECTION_REFRESH.match(path)
        if m:
            self._handle_section_refresh(m.group("session_id"), m.group("section"))
            return

        m = _RE_SAVE.match(path)
        if m:
            self._handle_save(m.group("session_id"))
            return

        m = _RE_RERUN.match(path)
        if m:
            self._handle_rerun(m.group("session_id"))
            return

        if _RE_SHARE_EMAIL.match(path):
            self._handle_share_email()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    # ── PUT ──────────────────────────────────────────────────────────────────
    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if _RE_SETTINGS.match(path):
            self._handle_settings_put()
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    # ── PATCH ────────────────────────────────────────────────────────────────
    def do_PATCH(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        m = _RE_INTENT.match(path)
        if m:
            self._handle_patch_intent(m.group("session_id"))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    # ── DELETE ───────────────────────────────────────────────────────────────
    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path == "/api/history":
            self._handle_history_clear()
            return

        m = _RE_HISTORY_DETAIL.match(path)
        if m:
            self._handle_history_delete(m.group("session_id"))
            return

        self.send_error(HTTPStatus.NOT_FOUND, "Endpoint not found")

    def _handle_stream(self, session_id: str) -> None:
        """GET /api/briefing/{id}/stream — SSE: emits one JSON event per agent."""
        intent = _get_intent(session_id)
        if not intent:
            self.send_error(HTTPStatus.NOT_FOUND, "Session not found")
            return

        sections: list[str] = intent.get("sections", [])

        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type",  "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        # Run each agent in its own thread; collect results via a queue
        result_q: queue.Queue = queue.Queue()

        def _run_section(sec: str) -> None:
            try:
                result = orchestrator.run_section(sec, intent)
            except Exception as exc:
                result = {
                    "section": sec, "status": "error",
                    "error": {"code": "agent_error", "message": str(exc)},
                }
            result_q.put(result)

        threads = [threading.Thread(target=_run_section, args=(s,), daemon=True) for s in sections]
        for t in threads:
            t.start()

        received = 0
        total = len(sections)
        try:
            while received < total:
                try:
                    result = result_q.get(timeout=35)
                except queue.Empty:
                    break
                payload = json.dumps(result, default=str)
                self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
                self.wfile.flush()
                received += 1

            # Terminal event so the client knows the stream is done
            self.wfile.write(b'data: {"event": "done"}\n\n')
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass  # client disconnected

    # ── Settings handlers ────────────────────────────────────────────────────

    def _handle_settings_get(self) -> None:
        """GET /api/settings"""
        self._send_json(HTTPStatus.OK, settings_manager.load())

    def _handle_settings_put(self) -> None:
        """PUT /api/settings"""
        try:
            body = self._read_json_body()
            updated = settings_manager.save(body)
            self._send_json(HTTPStatus.OK, updated)
        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    # ── Route handlers ───────────────────────────────────────────────────────

    def _handle_briefing(self) -> None:
        """POST /api/briefing — main entry point (agentic loop)."""
        try:
            body    = self._read_json_body()
            query   = str(body.get("query", "")).strip()
            user_id = str(body.get("user_id", "guest")).strip() or "guest"

            if not query:
                raise ValueError("Please enter what you would like in your briefing.")

            session_id = session_manager.start_session(user_id)

            result_box: dict = {}
            error_box:  list = []

            def _run() -> None:
                try:
                    result_box["data"] = orchestrator.run_agentic(
                        query, session_id=session_id
                    )
                except Exception as exc:
                    error_box.append(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=45)

            if error_box:
                raise error_box[0]
            if "data" not in result_box:
                raise TimeoutError(
                    "The briefing took too long. Check your network connection and try again."
                )

            agentic = result_box["data"]

            self._send_json(HTTPStatus.OK, {
                "session_id":       agentic.get("session_id", session_id),
                "intent":           agentic.get("intent", {}),
                "sections":         agentic.get("sections", {}),
                "briefing":         agentic.get("summary", ""),
                "loop_trace":       agentic.get("loop_trace", []),
                "reflection":       agentic.get("reflection", {}),
                "summary":          agentic.get("summary", ""),
                "tools_discovered": agentic.get("tools_discovered", {}),
            })

        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Could not create the briefing: {exc}"},
            )

    def _handle_commute_direct(self) -> None:
        """POST /api/commute — direct routing bypass."""
        try:
            body = self._read_json_body()
            location = str(body.get("from", "")).strip()
            destination = str(body.get("to", "")).strip()
            mode = str(body.get("mode", "drive")).strip()

            if not location:
                raise ValueError("Origin location is required.")

            result_box: dict = {}
            error_box: list = []

            def _run() -> None:
                try:
                    result_box["data"] = orchestrator.commute_agent.run_structured(
                        location, destination=destination, mode=mode
                    )
                except Exception as exc:
                    error_box.append(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=25)

            if error_box:
                raise error_box[0]
            if "data" not in result_box:
                raise TimeoutError("Commute routing timed out.")

            self._send_json(HTTPStatus.OK, result_box["data"])

        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Could not calculate commute: {exc}"},
            )

    def _handle_itinerary_direct(self) -> None:
        """POST /api/itinerary — direct itinerary generation bypass."""
        try:
            body = self._read_json_body()
            location = str(body.get("location", "")).strip() or str(body.get("destination", "")).strip()
            days = int(body.get("days", 3))
            budget = str(body.get("budget", "moderate")).strip()
            interests = body.get("interests", ["Sightseeing", "Food", "Culture"])

            if not location:
                raise ValueError("Destination location is required.")

            result_box: dict = {}
            error_box: list = []

            def _run() -> None:
                try:
                    result_box["data"] = orchestrator.itinerary_agent.run_structured(
                        location, days=days, budget=budget, interests=interests
                    )
                except Exception as exc:
                    error_box.append(exc)

            t = threading.Thread(target=_run, daemon=True)
            t.start()
            t.join(timeout=35)

            if error_box:
                raise error_box[0]
            if "data" not in result_box:
                raise TimeoutError("Itinerary generation timed out.")

            self._send_json(HTTPStatus.OK, result_box["data"])

        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Could not generate itinerary: {exc}"},
            )

    def _handle_section_refresh(self, session_id: str, section: str) -> None:
        """POST /api/briefing/{id}/{section}/refresh"""
        intent = _get_intent(session_id)
        result = orchestrator.run_section(section, intent)
        self._send_json(HTTPStatus.OK, result)

    def _handle_section_poll(self, session_id: str, section: str) -> None:
        """GET /api/briefing/{id}/{section}"""
        intent = _get_intent(session_id)
        if not intent:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {
                    "section": section,
                    "status":  "error",
                    "error":   {"code": "session_not_found", "message": "Session not found."},
                },
            )
            return
        result = orchestrator.run_section(section, intent)
        self._send_json(HTTPStatus.OK, result)

    def _handle_save(self, session_id: str) -> None:
        """POST /api/briefing/{id}/save — pin the current briefing."""
        intent = _get_intent(session_id)
        if not intent:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"saved": False, "error": {"code": "session_not_found", "message": "Session not found."}},
            )
            return

        sections: dict = {}
        for sec in intent.get("sections", []):
            sections[sec] = orchestrator.run_section(sec, intent)

        ok = session_manager.save_briefing(session_id, sections)
        if ok:
            self._send_json(HTTPStatus.OK, {"saved": True, "session_id": session_id})
        else:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"saved": False, "error": {"code": "write_failed", "message": "Briefing not saved — retry?"}},
            )

    def _handle_rerun(self, session_id: str) -> None:
        """POST /api/briefing/{id}/rerun — re-run all agents with the stored intent."""
        intent = _get_intent(session_id)
        if not intent:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "session_not_found", "message": "Session not found."}},
            )
            return

        results: dict = {}
        for sec in intent.get("sections", []):
            results[sec] = orchestrator.run_section(sec, intent)

        session_manager.log_interaction(session_id, {"event": "rerun", "sections": list(results.keys())})
        self._send_json(HTTPStatus.OK, {"session_id": session_id, "intent": intent, "sections": results})

    def _handle_patch_intent(self, session_id: str) -> None:
        """PATCH /api/briefing/{id}/intent — update intent fields and persist."""
        try:
            body   = self._read_json_body()
            intent = _get_intent(session_id)
            if not intent:
                intent = {}

            for field in ("location", "destination", "sections", "ingredients", "time_constraint", "travel_intent"):
                if field in body:
                    intent[field] = body[field]

            session_manager.save_intent(session_id, intent)
            self._send_json(HTTPStatus.OK, {"session_id": session_id, "intent": intent})

        except (ValueError, json.JSONDecodeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})

    def _handle_share_email(self) -> None:
        """POST /api/share/email — dispatch email briefing/itinerary via Gmail FastMCP tool."""
        try:
            body = self._read_json_body()
            to_email = str(body.get("to_email", "")).strip() or Config.get_recipient_email()
            subject  = str(body.get("subject", "")).strip() or "Travel Itinerary & Briefing"
            body_html = str(body.get("body_html", "")).strip()
            body_text = str(body.get("body_text", "")).strip()

            if not to_email or "@" not in to_email:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Valid recipient email address is required (or set RECIPIENT_EMAIL in .env)."})
                return

            if not body_html and not body_text:
                session_id = str(body.get("session_id", "")).strip()
                intent = _get_intent(session_id)
                loc = intent.get("location", "your destination")
                body_html = f"<h2>Briefing & Itinerary for {loc}</h2><p>Here is your travel summary from LetGO.</p>"
                body_text = f"Briefing & Itinerary for {loc}\nHere is your travel summary from LetGO."

            from mcp_tools.email_tools import send_email_briefing
            res = send_email_briefing(
                to_email=to_email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
            )
            self._send_json(HTTPStatus.OK, {"success": True, "result": res})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _handle_history_list(self) -> None:
        """GET /api/history"""
        try:
            sessions = session_manager.list_sessions(limit=20)
            self._send_json(HTTPStatus.OK, {"sessions": sessions})
        except Exception as exc:
            self._send_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": f"Could not load history: {exc}"},
            )

    def _handle_history_detail(self, session_id: str) -> None:
        """GET /api/history/{session_id}"""
        data = session_manager.get_session(session_id)
        if data is None:
            self._send_json(
                HTTPStatus.NOT_FOUND,
                {"error": {"code": "not_found", "message": f"Session {session_id!r} not found."}},
            )
            return
        self._send_json(HTTPStatus.OK, data)

    def _handle_history_delete(self, session_id: str) -> None:
        """DELETE /api/history/{session_id}"""
        try:
            ok = session_manager.delete_session(session_id)
            if ok:
                self._send_json(HTTPStatus.OK, {"deleted": True, "session_id": session_id})
            else:
                self._send_json(HTTPStatus.NOT_FOUND, {"error": "Session not found or could not be deleted"})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _handle_history_clear(self) -> None:
        """DELETE /api/history"""
        try:
            ok = session_manager.clear_history()
            if ok:
                self._send_json(HTTPStatus.OK, {"cleared": True})
            else:
                self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "Could not clear history"})
        except Exception as exc:
            self._send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": str(exc)})

    def _handle_observability_metrics(self) -> None:
        """GET /api/observability/metrics"""
        self._send_json(HTTPStatus.OK, telemetry.metrics.snapshot())

    def _handle_observability_traces(self) -> None:
        """GET /api/observability/traces"""
        self._send_json(HTTPStatus.OK, {"traces": list(telemetry.recent_traces)})

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def _send_json(self, status: HTTPStatus, payload: dict) -> None:
        encoded = json.dumps(payload, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type",   "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)


if __name__ == "__main__":
    from services.config import Config
    server = ThreadingHTTPServer(("127.0.0.1", 8000), CommuteCommanderHandler)
    model = Config.get_llm_model() or "llama-3.1-8b-instruct"
    
    print("\n" + "\033[1m\033[36m" + "═" * 65 + "\033[0m")
    print(" \033[1m\033[32m🚀 LetGO — Multi-Agent Assistant Server\033[0m")
    print("\033[1m\033[36m" + "═" * 65 + "\033[0m")
    print(" • \033[1mWeb UI URL\033[0m         : \033[34mhttp://localhost:8000\033[0m")
    print(" • \033[1mObservability API\033[0m  : \033[34mhttp://localhost:8000/api/observability/metrics\033[0m")
    print(" • \033[1mRecent Traces API\033[0m  : \033[34mhttp://localhost:8000/api/observability/traces\033[0m")
    print(" • \033[1mTelemetry Logs\033[0m     : \033[33mdata/telemetry/app.log\033[0m & \033[33mtraces.jsonl\033[0m")
    print(f" • \033[1mActive Model\033[0m       : \033[35m{model}\033[0m")
    print("\033[1m\033[36m" + "═" * 65 + "\033[0m")
    print(" \033[90m[INFO] Telemetry active. Ready & listening for requests...\033[0m\n", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\033[33mServer stopped.\033[0m")
    finally:
        server.server_close()

