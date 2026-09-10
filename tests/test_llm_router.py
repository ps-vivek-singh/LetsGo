"""Unit tests for LLM-driven routing and tool selection (Phase 8B / LLM-Driven Router).

Validates:
- LLMRouter route_query using LLMClient intent parsing
- LLMRouter fallback to deterministic keyword router when offline or unavailable
- AgenticLoop LLM-driven tool selection (perceive -> plan -> act -> observe -> decide)
- AgenticLoop explicit stop decision when LLM returns 'finish'
- Parameter passing from LLM to target tool
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure src/ is on the path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from agents.agentic_loop import AgenticLoop
from agents.orchestrator import OrchestratorAgent
from agents.router import LLMRouter, Router
from services.llm_client import LLMClient


class TestLLMRouter(unittest.TestCase):
    """Test LLMRouter intent routing and fallback behavior."""

    def test_llm_router_uses_llm_when_available(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = True
        mock_llm.route_intent.return_value = {
            "sections": ["weather", "commute"],
            "thought": "User wants weather and commute route.",
        }

        router = LLMRouter(llm_client=mock_llm)
        routes = router.route_query("Weather and drive to airport", discovered_tools={"weather": ["get_weather"], "commute": ["get_commute_route"]})

        self.assertIn("weather", routes)
        self.assertIn("commute", routes)
        mock_llm.route_intent.assert_called_once()

    def test_llm_router_falls_back_when_llm_unavailable(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = False

        router = LLMRouter(llm_client=mock_llm)
        routes = router.route_query("Weather and commute", fallback_sections=["weather"])

        self.assertEqual(routes, ["weather"])
        mock_llm.route_intent.assert_not_called()

    def test_llm_router_falls_back_on_llm_exception(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = True
        mock_llm.route_intent.side_effect = RuntimeError("API connection timeout")

        router = LLMRouter(llm_client=mock_llm)
        routes = router.route_query("Weather forecast", fallback_sections=["weather"])

        self.assertEqual(routes, ["weather"])


class TestLLMDrivenAgenticLoop(unittest.TestCase):
    """Test agentic loop execution driven by LLM decisions."""

    def setUp(self):
        self.orchestrator = OrchestratorAgent()

    def test_llm_loop_executes_tool_and_finishes(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = True
        mock_llm.select_next_action.side_effect = [
            {
                "thought": "I will call get_weather for Chicago.",
                "action": "weather.get_weather",
                "action_args": {"location": "Chicago"},
            },
            {
                "thought": "All requested info gathered. Finishing.",
                "action": "finish",
                "action_args": {},
            },
        ]

        loop = AgenticLoop(
            server_registry=self.orchestrator.server_registry,
            parser=self.orchestrator.parser,
            router=self.orchestrator.router,
            llm_client=mock_llm,
        )

        result = loop.run("Weather from Chicago")

        self.assertIn("weather", result.sections)
        self.assertEqual(result.sections["weather"]["status"], "success")

        # Check trace
        actions = [step.action for step in result.trace]
        self.assertIn("weather.get_weather", actions)
        self.assertIn("finish_complete", actions)
        self.assertEqual(mock_llm.select_next_action.call_count, 2)

    def test_llm_loop_multi_tool_sequence(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = True
        mock_llm.select_next_action.side_effect = [
            {
                "thought": "First, get weather for London.",
                "action": "weather.get_weather",
                "action_args": {"location": "London"},
            },
            {
                "thought": "Next, get news headlines for London.",
                "action": "news.get_headlines",
                "action_args": {"location": "London"},
            },
            {
                "thought": "Both weather and news retrieved. Stopping.",
                "action": "finish",
                "action_args": {},
            },
        ]

        loop = AgenticLoop(
            server_registry=self.orchestrator.server_registry,
            parser=self.orchestrator.parser,
            router=self.orchestrator.router,
            llm_client=mock_llm,
        )

        result = loop.run("Weather and news for London")

        self.assertIn("weather", result.sections)
        self.assertIn("news", result.sections)
        self.assertEqual(mock_llm.select_next_action.call_count, 3)

    def test_llm_loop_passes_discovered_tools_manifest(self):
        mock_llm = MagicMock(spec=LLMClient)
        mock_llm.is_available.return_value = True
        mock_llm.select_next_action.return_value = {
            "thought": "Nothing to do.",
            "action": "finish",
            "action_args": {},
        }

        loop = AgenticLoop(
            server_registry=self.orchestrator.server_registry,
            parser=self.orchestrator.parser,
            router=self.orchestrator.router,
            llm_client=mock_llm,
        )

        loop.run("Quick check")

        # Verify select_next_action received tools_manifest
        call_kwargs = mock_llm.select_next_action.call_args.kwargs
        self.assertIn("tools_manifest", call_kwargs)
        manifest = call_kwargs["tools_manifest"]
        self.assertIn("weather", manifest)
        self.assertIn("news", manifest)


if __name__ == "__main__":
    unittest.main()
