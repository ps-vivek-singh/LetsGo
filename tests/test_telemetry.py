"""Tests for Central Telemetry, Logging & Observability Engine."""
import json
import time
from pathlib import Path
from services.telemetry import Telemetry, MetricsRegistry, Span


def test_metrics_registry_snapshot():
    registry = MetricsRegistry()
    registry.record_http_request("GET", "/api/history", 200, 15.5)
    registry.record_http_request("POST", "/api/briefing", 200, 120.0)
    registry.record_agent_execution("weather_agent")
    registry.record_tool_call("weather", "get_weather", 45.0, status="success")
    registry.record_llm_call("nim", "meta/llama-3.1-8b-instruct", prompt_tokens=50, completion_tokens=100)
    registry.record_reflection_override()
    registry.record_error("tool_timeout")

    snapshot = registry.snapshot()

    assert snapshot["http"]["total_requests"] == 2
    assert "GET /api/history -> 200" in snapshot["http"]["endpoints"]
    assert snapshot["agents"]["executions"]["weather_agent"] == 1
    assert snapshot["agents"]["reflection_overrides"] == 1
    assert snapshot["tools"]["avg_latencies_ms"]["weather.get_weather"] == 45.0
    assert snapshot["llm"]["tokens"]["total"] == 150
    assert snapshot["errors"]["tool_timeout"] == 1


def test_span_context_manager():
    telemetry = Telemetry(log_to_file=False)

    with telemetry.span("test_operation", trace_id="trace-123") as span:
        span.set_attribute("key", "value")
        time.sleep(0.01)

    assert span.status == "OK"
    assert span.duration_ms >= 8.0  # at least ~10ms
    assert span.attributes["key"] == "value"
    assert span.trace_id == "trace-123"


def test_span_error_handling():
    telemetry = Telemetry(log_to_file=False)

    try:
        with telemetry.span("failing_operation", trace_id="trace-err") as span:
            raise ValueError("Something broke")
    except ValueError:
        pass

    assert span.status == "ERROR"
    assert "Something broke" in (span.error or "")


def test_telemetry_trace_recording(tmp_path):
    telemetry = Telemetry(log_to_file=False)

    sample_trace = {
        "session_id": "test-session",
        "query": "Weather in London",
        "steps": [{"step": 1, "action": "get_weather"}],
    }
    telemetry.record_trace(sample_trace)

    assert len(telemetry.recent_traces) == 1
    assert telemetry.recent_traces[0]["session_id"] == "test-session"
    assert "timestamp" in telemetry.recent_traces[0]


def test_telemetry_logging_methods(capsys):
    telemetry = Telemetry(log_to_file=False)
    telemetry.http("POST", "/api/briefing", 200, 45.2, trace_id="tid-1")
    telemetry.agent("Dispatched WeatherAgent", trace_id="tid-1", agent_name="weather_agent")
    telemetry.tool("weather", "get_weather", 30.1, status="OK", trace_id="tid-1")
    telemetry.reflection("Rule triggered", trace_id="tid-1", overrides_count=1)
    telemetry.llm("groq", "llama-3.3-70b-versatile", 85.0, 100, 200, trace_id="tid-1")
    telemetry.error("HTTP", "Not found", trace_id="tid-1")

    captured = capsys.readouterr().out
    assert "[HTTP]" in captured
    assert "[AGENT]" in captured
    assert "[TOOL]" in captured
    assert "[REFLECTION]" in captured
    assert "[LLM]" in captured
    assert "[ERROR]" in captured
