"""Integration test for webapp.py observability endpoints."""
import json
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from scripts.webapp import CommuteCommanderHandler


def test_webapp_observability_endpoints():
    server = ThreadingHTTPServer(("127.0.0.1", 8899), CommuteCommanderHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.2)

    try:
        # Test GET /api/observability/metrics
        req_metrics = urllib.request.Request("http://127.0.0.1:8899/api/observability/metrics")
        with urllib.request.urlopen(req_metrics, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "http" in data
            assert "agents" in data
            assert "tools" in data
            assert "llm" in data

        # Test GET /api/observability/traces
        req_traces = urllib.request.Request("http://127.0.0.1:8899/api/observability/traces")
        with urllib.request.urlopen(req_traces, timeout=5) as resp:
            assert resp.status == 200
            data = json.loads(resp.read().decode("utf-8"))
            assert "traces" in data
            assert isinstance(data["traces"], list)

    finally:
        server.shutdown()
        server.server_close()
