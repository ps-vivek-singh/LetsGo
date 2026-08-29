"""Central Observability, Telemetry & Logging Engine.

Provides:
- Dual-mode logging: ANSI color-coded terminal output + structured JSONL disk logs
- Distributed Tracing & Span context managers with unique trace_ids
- In-memory Metrics Registry tracking HTTP, Agent, Tool, and LLM telemetry
- Trace recording buffer for observability inspection and dashboard visualization
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Generator, List, Optional


# ── ANSI Terminal Colors ──────────────────────────────────────────────────
class _Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


_IS_WINDOWS_TERM = sys.platform.startswith("win")
if _IS_WINDOWS_TERM:
    # Enable ANSI escape sequences on Windows console if available
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


# ── Directory Config ──────────────────────────────────────────────────────
_TELEMETRY_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "telemetry"
_APP_LOG_PATH = _TELEMETRY_DIR / "app.log"
_TRACES_LOG_PATH = _TELEMETRY_DIR / "traces.jsonl"


# ── Metrics Registry ──────────────────────────────────────────────────────
class MetricsRegistry:
    """In-memory metrics collector for request rates, latencies, and agent statistics."""

    def __init__(self) -> None:
        self.http_requests_total: Dict[str, int] = defaultdict(int)
        self.http_latencies_ms: List[float] = []
        self.agent_executions_total: Dict[str, int] = defaultdict(int)
        self.tool_calls_total: Dict[str, int] = defaultdict(int)
        self.tool_latencies_ms: Dict[str, List[float]] = defaultdict(list)
        self.llm_calls_total: Dict[str, int] = defaultdict(int)
        self.llm_tokens_total: Dict[str, int] = defaultdict(int)
        self.reflection_overrides_total: int = 0
        self.errors_total: Dict[str, int] = defaultdict(int)
        self._start_time = time.time()

    def record_http_request(self, method: str, path: str, status_code: int, duration_ms: float) -> None:
        key = f"{method.upper()} {path} -> {status_code}"
        self.http_requests_total[key] += 1
        self.http_latencies_ms.append(duration_ms)
        if len(self.http_latencies_ms) > 1000:
            self.http_latencies_ms.pop(0)

    def record_agent_execution(self, agent_name: str) -> None:
        self.agent_executions_total[agent_name] += 1

    def record_tool_call(self, server_name: str, tool_name: str, duration_ms: float, status: str = "success") -> None:
        key = f"{server_name}.{tool_name} [{status}]"
        self.tool_calls_total[key] += 1
        self.tool_latencies_ms[f"{server_name}.{tool_name}"].append(duration_ms)
        if len(self.tool_latencies_ms[f"{server_name}.{tool_name}"]) > 500:
            self.tool_latencies_ms[f"{server_name}.{tool_name}"].pop(0)

    def record_llm_call(self, provider: str, model: str, prompt_tokens: int = 0, completion_tokens: int = 0, status: str = "success") -> None:
        key = f"{provider}/{model} [{status}]"
        self.llm_calls_total[key] += 1
        self.llm_tokens_total["prompt"] += prompt_tokens
        self.llm_tokens_total["completion"] += completion_tokens
        self.llm_tokens_total["total"] += (prompt_tokens + completion_tokens)

    def record_reflection_override(self) -> None:
        self.reflection_overrides_total += 1

    def record_error(self, error_type: str) -> None:
        self.errors_total[error_type] += 1

    def snapshot(self) -> Dict[str, Any]:
        """Return a structured summary of all tracked metrics."""
        uptime_seconds = round(time.time() - self._start_time, 1)

        http_avg_lat = round(sum(self.http_latencies_ms) / len(self.http_latencies_ms), 2) if self.http_latencies_ms else 0.0
        http_p95_lat = 0.0
        if self.http_latencies_ms:
            sorted_lat = sorted(self.http_latencies_ms)
            p95_idx = int(len(sorted_lat) * 0.95)
            http_p95_lat = round(sorted_lat[min(p95_idx, len(sorted_lat) - 1)], 2)

        tool_avg_latencies: Dict[str, float] = {}
        for tool, lats in self.tool_latencies_ms.items():
            if lats:
                tool_avg_latencies[tool] = round(sum(lats) / len(lats), 2)

        return {
            "uptime_seconds": uptime_seconds,
            "http": {
                "total_requests": sum(self.http_requests_total.values()),
                "endpoints": dict(self.http_requests_total),
                "avg_latency_ms": http_avg_lat,
                "p95_latency_ms": http_p95_lat,
            },
            "agents": {
                "executions": dict(self.agent_executions_total),
                "reflection_overrides": self.reflection_overrides_total,
            },
            "tools": {
                "invocations": dict(self.tool_calls_total),
                "avg_latencies_ms": tool_avg_latencies,
            },
            "llm": {
                "calls": dict(self.llm_calls_total),
                "tokens": dict(self.llm_tokens_total),
            },
            "errors": dict(self.errors_total),
        }


# ── Trace Record ──────────────────────────────────────────────────────────
class Span:
    """Represents a discrete unit of work within a trace."""

    def __init__(self, name: str, trace_id: str, parent_id: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None) -> None:
        self.span_id = uuid.uuid4().hex[:8]
        self.trace_id = trace_id
        self.parent_id = parent_id
        self.name = name
        self.attributes = attributes or {}
        self.start_time = time.perf_counter()
        self.end_time: Optional[float] = None
        self.duration_ms: float = 0.0
        self.status = "UNSET"
        self.error: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> None:
        self.attributes[key] = value

    def finish(self, status: str = "OK", error: Optional[str] = None) -> None:
        self.end_time = time.perf_counter()
        self.duration_ms = round((self.end_time - self.start_time) * 1000, 2)
        self.status = status
        self.error = error


# ── Telemetry Engine ──────────────────────────────────────────────────────
class Telemetry:
    """Unified logger, tracer, and metrics engine."""

    def __init__(self, log_to_file: bool = True) -> None:
        self.metrics = MetricsRegistry()
        self.recent_traces: deque = deque(maxlen=50)
        self.log_to_file = log_to_file

        if self.log_to_file:
            os.makedirs(_TELEMETRY_DIR, exist_ok=True)

    # ── Console & JSON Logging ─────────────────────────────────────────────

    def _format_time(self) -> str:
        return datetime.now().strftime("%H:%M:%S.%f")[:-3]

    def _write_json_log(self, record: Dict[str, Any]) -> None:
        if not self.log_to_file:
            return
        try:
            with open(_APP_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    def log(self, level: str, category: str, message: str, trace_id: str = "", **kwargs: Any) -> None:
        """Emit formatted terminal log and JSON disk log."""
        timestamp = self._format_time()
        tid_str = f" [{_Colors.DIM}tid:{trace_id[:8]}{_Colors.RESET}]" if trace_id else ""

        # Color mapping by category
        cat_color = _Colors.CYAN
        if category.upper() == "HTTP":
            cat_color = _Colors.GREEN
        elif category.upper() == "AGENT":
            cat_color = _Colors.MAGENTA
        elif category.upper() == "TOOL":
            cat_color = _Colors.YELLOW
        elif category.upper() == "REFLECTION":
            cat_color = _Colors.BLUE
        elif category.upper() == "LLM":
            cat_color = _Colors.CYAN
        elif category.upper() in ("ERROR", "EXCEPTION"):
            cat_color = _Colors.RED

        # Terminal format
        level_tag = f"[{level.upper()}]"
        if level.upper() == "ERROR":
            level_tag = f"{_Colors.RED}[ERROR]{_Colors.RESET}"
        elif level.upper() == "WARN":
            level_tag = f"{_Colors.YELLOW}[WARN]{_Colors.RESET}"
        else:
            level_tag = f"{_Colors.DIM}[{level.upper()}]{_Colors.RESET}"

        cat_badge = f"{cat_color}[{category.upper()}]{_Colors.RESET}"
        
        extra_str = ""
        if kwargs:
            extra_parts = [f"{_Colors.DIM}{k}={_Colors.RESET}{v}" for k, v in kwargs.items()]
            extra_str = " (" + ", ".join(extra_parts) + ")"

        print(f"{_Colors.GRAY}{timestamp}{_Colors.RESET} {level_tag} {cat_badge}{tid_str} {message}{extra_str}", flush=True)

        # File JSON format
        self._write_json_log({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "category": category.upper(),
            "trace_id": trace_id,
            "message": message,
            **kwargs,
        })

    def http(self, method: str, path: str, status: int, duration_ms: float, trace_id: str = "", ip: str = "127.0.0.1") -> None:
        """Log an incoming HTTP request."""
        status_color = _Colors.GREEN if status < 400 else (_Colors.YELLOW if status < 500 else _Colors.RED)
        msg = f"{method.upper():<6} {path} {_Colors.BOLD}{status_color}{status}{_Colors.RESET} ({duration_ms:.1f}ms)"
        self.log("INFO", "HTTP", msg, trace_id=trace_id, duration_ms=duration_ms, status=status, ip=ip)
        self.metrics.record_http_request(method, path, status, duration_ms)

    def agent(self, message: str, trace_id: str = "", agent_name: str = "", **kwargs: Any) -> None:
        """Log an agent lifecycle event."""
        self.log("INFO", "AGENT", message, trace_id=trace_id, agent=agent_name, **kwargs)
        if agent_name:
            self.metrics.record_agent_execution(agent_name)

    def tool(self, server_name: str, tool_name: str, duration_ms: float, status: str = "OK", trace_id: str = "", **kwargs: Any) -> None:
        """Log a FastMCP tool execution."""
        status_tag = f"{_Colors.GREEN}OK{_Colors.RESET}" if status.upper() == "OK" else f"{_Colors.RED}{status}{_Colors.RESET}"
        msg = f"Invoke {_Colors.BOLD}{server_name}.{tool_name}{_Colors.RESET} -> {status_tag} ({duration_ms:.1f}ms)"
        self.log("INFO", "TOOL", msg, trace_id=trace_id, server=server_name, tool=tool_name, duration_ms=duration_ms, status=status, **kwargs)
        self.metrics.record_tool_call(server_name, tool_name, duration_ms, status=status)

    def reflection(self, message: str, trace_id: str = "", overrides_count: int = 0) -> None:
        """Log a cross-domain reflection event."""
        self.log("INFO", "REFLECTION", message, trace_id=trace_id, overrides=overrides_count)
        if overrides_count > 0:
            for _ in range(overrides_count):
                self.metrics.record_reflection_override()

    def llm(self, provider: str, model: str, duration_ms: float, prompt_tokens: int = 0, completion_tokens: int = 0, status: str = "OK", trace_id: str = "") -> None:
        """Log an LLM completion invocation."""
        token_info = f"{prompt_tokens + completion_tokens} tokens" if (prompt_tokens or completion_tokens) else "stream"
        msg = f"{provider}/{model} ({duration_ms:.1f}ms, {token_info}) -> {status}"
        self.log("INFO", "LLM", msg, trace_id=trace_id, provider=provider, model=model, duration_ms=duration_ms, tokens=prompt_tokens + completion_tokens)
        self.metrics.record_llm_call(provider, model, prompt_tokens, completion_tokens, status=status)

    def error(self, category: str, message: str, trace_id: str = "", exc: Optional[Exception] = None, **kwargs: Any) -> None:
        """Log an error with optional exception traceback."""
        exc_str = f" | {exc}" if exc else ""
        self.log("ERROR", category, f"{message}{exc_str}", trace_id=trace_id, **kwargs)
        self.metrics.record_error(category)

    # ── Spans & Tracing ───────────────────────────────────────────────────

    @contextmanager
    def span(self, name: str, trace_id: Optional[str] = None, parent_id: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None) -> Generator[Span, None, None]:
        """Context manager to measure and track an execution span."""
        tid = trace_id or uuid.uuid4().hex
        s = Span(name=name, trace_id=tid, parent_id=parent_id, attributes=attributes)
        try:
            yield s
            s.finish(status="OK")
        except Exception as exc:
            s.finish(status="ERROR", error=str(exc))
            raise

    def record_trace(self, trace_payload: Dict[str, Any]) -> None:
        """Store a completed agent trajectory in memory and on disk."""
        payload_with_time = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **trace_payload,
        }
        self.recent_traces.appendleft(payload_with_time)

        if self.log_to_file:
            try:
                with open(_TRACES_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(payload_with_time, default=str) + "\n")
            except Exception:
                pass


# ── Global Singleton Instance ─────────────────────────────────────────────
telemetry = Telemetry()
