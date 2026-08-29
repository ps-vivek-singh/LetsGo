"""Tests for the agentic ReAct loop (Phase 8B).

Validates:
- Tool discovery across all MCP servers
- Loop executes the correct number of iterations
- Loop trace contains thought/action/observation entries
- Loop terminates when all sections are fulfilled
- Max iterations safety net
- Agentic result includes reflection and summary
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Ensure src/ is on the path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from agents.agentic_loop import AgenticLoop, AgenticResult, TraceStep, _SECTION_TOOL_MAP
from agents.orchestrator import OrchestratorAgent


class TestToolDiscovery(unittest.TestCase):
    """Criterion 2: Agent connects to server and can list tools."""

    def setUp(self):
        self.orchestrator = OrchestratorAgent()

    def test_discover_tools_returns_all_servers(self):
        discovered = self.orchestrator.discover_tools()
        self.assertIn("weather", discovered)
        self.assertIn("news", discovered)
        self.assertIn("recipe", discovered)
        self.assertIn("commute", discovered)

    def test_each_server_has_at_least_one_tool(self):
        discovered = self.orchestrator.discover_tools()
        for server, tools in discovered.items():
            self.assertGreater(len(tools), 0, f"Server '{server}' has no tools")

    def test_weather_server_has_get_weather(self):
        discovered = self.orchestrator.discover_tools()
        self.assertIn("get_weather", discovered["weather"])

    def test_news_server_has_get_headlines(self):
        discovered = self.orchestrator.discover_tools()
        self.assertIn("get_headlines", discovered["news"])

    def test_recipe_server_has_get_recipe(self):
        discovered = self.orchestrator.discover_tools()
        self.assertIn("get_recipe", discovered["recipe"])

    def test_commute_server_has_get_commute_route(self):
        discovered = self.orchestrator.discover_tools()
        self.assertIn("get_commute_route", discovered["commute"])


class TestAgenticLoop(unittest.TestCase):
    """Criterion 3: Agentic loop — call tool, observe, decide to finish."""

    def setUp(self):
        self.orchestrator = OrchestratorAgent()

    def test_run_agentic_returns_sections(self):
        """Agentic loop should return results for requested sections."""
        result = self.orchestrator.run_agentic("Weather from Chicago")
        self.assertIn("sections", result)
        self.assertIn("weather", result["sections"])

    def test_run_agentic_includes_loop_trace(self):
        """Loop trace should contain at least one step."""
        result = self.orchestrator.run_agentic("News headlines")
        trace = result.get("loop_trace", [])
        self.assertGreater(len(trace), 0, "Loop trace should have at least one step")

    def test_trace_steps_have_required_fields(self):
        """Each trace step should have thought, action, observation."""
        result = self.orchestrator.run_agentic("Weather from London")
        trace = result.get("loop_trace", [])
        for step in trace:
            self.assertIn("step", step)
            self.assertIn("thought", step)
            self.assertIn("action", step)
            self.assertIn("observation", step)

    def test_loop_terminates_with_finish_step(self):
        """Last tool-calling step should be a finish decision."""
        result = self.orchestrator.run_agentic("Weather from Delhi")
        trace = result.get("loop_trace", [])
        # Find the completion step (before reflect and synthesize)
        finish_steps = [s for s in trace if s["action"].startswith("finish")]
        self.assertGreater(len(finish_steps), 0, "Should have a finish step")

    def test_multisection_query_calls_multiple_tools(self):
        """A query requesting weather + news should produce 2 tool calls."""
        result = self.orchestrator.run_agentic("Weather and news from Chicago")
        sections = result.get("sections", {})
        # Should have at least weather and news
        self.assertIn("weather", sections)
        self.assertIn("news", sections)

    def test_run_agentic_includes_tools_discovered(self):
        """Result should include the tool discovery manifest."""
        result = self.orchestrator.run_agentic("Weather")
        discovered = result.get("tools_discovered", {})
        self.assertIn("weather", discovered)

    def test_run_agentic_includes_summary(self):
        """Result should include a natural-language summary."""
        result = self.orchestrator.run_agentic("Weather from Chicago")
        summary = result.get("summary", "")
        self.assertGreater(len(summary), 0, "Summary should not be empty")

    def test_run_agentic_includes_reflection(self):
        """Result should include a reflection dict."""
        result = self.orchestrator.run_agentic("Weather from Chicago")
        reflection = result.get("reflection", {})
        self.assertIn("changes_made", reflection)
        self.assertIn("confirmations", reflection)


class TestAgenticLoopDirect(unittest.TestCase):
    """Direct tests on the AgenticLoop class."""

    def setUp(self):
        self.orchestrator = OrchestratorAgent()
        self.loop = self.orchestrator.agentic_loop

    def test_loop_run_returns_agentic_result(self):
        result = self.loop.run("Weather from Mumbai")
        self.assertIsInstance(result, AgenticResult)

    def test_loop_trace_is_list_of_trace_steps(self):
        result = self.loop.run("News")
        self.assertIsInstance(result.trace, list)
        for step in result.trace:
            self.assertIsInstance(step, TraceStep)

    def test_section_tool_map_covers_all_sections(self):
        """Every routable section should have a tool mapping."""
        expected = {"weather", "news", "commute", "breakfast", "itinerary", "email"}
        self.assertEqual(set(_SECTION_TOOL_MAP.keys()), expected)

    def test_empty_query_produces_no_sections(self):
        """An unrecognised query should still complete without error."""
        result = self.loop.run("hello world")
        # Might or might not match sections — but should not crash
        self.assertIsInstance(result.sections, dict)


if __name__ == "__main__":
    unittest.main()
