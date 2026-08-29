from __future__ import annotations

from typing import Dict, List

from nlp.query_parser import QueryParser
from agents.agentic_loop import AgenticLoop
from agents.weather_agent import WeatherAgent
from agents.news_agent import NewsAgent
from agents.breakfast_agent import BreakfastAgent
from agents.commute_agent import CommuteAgent
from agents.itinerary_agent import ItineraryAgent
from agents.agent_registry import AgentRegistry
from agents.router import Router
from mcp_tools.real_mcp_server import RealMCPServer
from mcp_tools.server_registry import ServerRegistry
from mcp_tools.tool_registry import ToolRegistry
from mcp_tools.email_tools import send_email_briefing
from services.session_manager import SessionManager


class OrchestratorAgent:
    def __init__(self, session_manager: SessionManager | None = None) -> None:
        self.parser = QueryParser()
        self.session_manager = session_manager or SessionManager()
        self.weather_agent = WeatherAgent()
        self.news_agent = NewsAgent()
        self.breakfast_agent = BreakfastAgent()
        self.commute_agent = CommuteAgent()
        self.itinerary_agent = ItineraryAgent()
        self.router = Router()
        self.tool_registry = ToolRegistry()
        self.tool_registry.register("weather", self.weather_agent.tool)
        self.tool_registry.register("news", self.news_agent.tool)
        self.tool_registry.register("recipe", self.breakfast_agent.tool)
        self.tool_registry.register("commute", self.commute_agent.tool)
        self.tool_registry.register("itinerary", self.itinerary_agent.tool)

        self.agent_registry = AgentRegistry()
        self.agent_registry.register("weather", self.weather_agent)
        self.agent_registry.register("news", self.news_agent)
        self.agent_registry.register("breakfast", self.breakfast_agent)
        self.agent_registry.register("commute", self.commute_agent)
        self.agent_registry.register("itinerary", self.itinerary_agent)

        # ── MCP Server Registry ────────────────────────────────────────────
        # Each domain has its own RealMCPServer exposing the canonical tool
        # from that domain's MCP module. The orchestrator calls agents directly;
        # these server objects enable external MCP tool discovery / inspection.
        self.server_registry = ServerRegistry()

        self.weather_server = RealMCPServer("weather-server")
        self.news_server = RealMCPServer("news-server")
        self.recipe_server = RealMCPServer("recipe-server")
        self.commute_server = RealMCPServer("commute-server")
        self.itinerary_server = RealMCPServer("itinerary-server")
        self.gmail_server = RealMCPServer("gmail-server")

        self.weather_server.register_tool("get_weather", self.weather_agent.tool.get_weather)
        self.news_server.register_tool("get_headlines", self.news_agent.tool.get_headlines)
        self.recipe_server.register_tool("get_recipe", self.breakfast_agent.tool.get_recipe)
        # Register the full routing tool (not the legacy advice shim)
        self.commute_server.register_tool("get_commute_route", self.commute_agent.tool.get_commute_route)
        from mcp_tools.itinerary_tools import get_itinerary
        self.itinerary_server.register_tool("get_itinerary", get_itinerary)
        self.gmail_server.register_tool("send_email_briefing", send_email_briefing)

        self.server_registry.register("weather", self.weather_server)
        self.server_registry.register("news", self.news_server)
        self.server_registry.register("recipe", self.recipe_server)
        self.server_registry.register("commute", self.commute_server)
        self.server_registry.register("itinerary", self.itinerary_server)
        self.server_registry.register("gmail", self.gmail_server)

        # ── Agentic Loop ──────────────────────────────────────────────────
        self.agentic_loop = AgenticLoop(
            server_registry=self.server_registry,
            parser=self.parser,
            router=self.router,
        )

    # ------------------------------------------------------------------
    # Original plain-text run — preserved so CLI and existing tests work
    # ------------------------------------------------------------------
    def run(self, query: str, session_id: str | None = None) -> str:
        """Run query through the agentic loop and return natural language summary."""
        result = self.run_agentic(query, session_id=session_id)
        summary = result.get("summary", "")
        if summary:
            return summary
        return "No matching sections were found. Try a request like: weather, news, commute, or breakfast."

    # ------------------------------------------------------------------
    # Structured run — used by the web UI for per-card JSON rendering
    # ------------------------------------------------------------------
    def run_structured(self, query: str, session_id: str | None = None) -> dict:
        """Parse the query and call each requested agent's run_structured().

        Returns::

            {
                "session_id": "...",
                "intent": {
                    "location":        str,
                    "destination":     str,   # extracted commute destination
                    "sections":        list,
                    "ingredients":     list,
                    "time_constraint": str,
                },
                "sections": {
                    "weather":   { section, status, data } | { section, status, error },
                    "news":      ...,
                    "commute":   ...,
                    "breakfast": ...,
                }
            }
        """
        parsed = self.parser.parse(query)
        location: str        = parsed.get("location", "")
        destination: str     = parsed.get("destination", "")   # ← extracted destination
        sections: list       = parsed.get("sections", [])
        ingredients: list    = parsed.get("ingredients", [])
        time_constraint      = parsed.get("time_constraint", "10 min")

        routed_agents = self.router.route(sections)
        results: dict = {}

        try:
            from services.telemetry import telemetry
            telemetry.agent(f"Orchestrator: structured run for query '{query}'", trace_id=session_id or "", agent_name="orchestrator")
            telemetry.agent(f"Intent parsed: loc='{location}', dest='{destination}', sections={sections}", trace_id=session_id or "")
        except Exception:
            telemetry = None

        if "weather" in routed_agents:
            if telemetry:
                telemetry.agent("Dispatching WeatherAgent", trace_id=session_id or "", agent_name="weather_agent")
            try:
                results["weather"] = self.weather_agent.run_structured(location)
            except Exception as exc:
                results["weather"] = {
                    "section": "weather",
                    "status": "error",
                    "error": {"code": "agent_error", "message": str(exc)},
                }

        if "news" in routed_agents:
            try:
                results["news"] = self.news_agent.run_structured()
            except Exception as exc:
                results["news"] = {
                    "section": "news",
                    "status": "error",
                    "error": {"code": "agent_error", "message": str(exc)},
                }

        if "commute" in routed_agents:
            try:
                # Pass the extracted destination — this is the core fix for
                # hardcoded routing. If destination is empty the commute tool
                # falls back to geocoding "{location} city centre".
                results["commute"] = self.commute_agent.run_structured(location, destination)
            except Exception as exc:
                results["commute"] = {
                    "section": "commute",
                    "status": "error",
                    "error": {"code": "agent_error", "message": str(exc)},
                }

        if "breakfast" in routed_agents or "meal" in routed_agents:
            try:
                meal_type = parsed.get("meal_type", "meal")
                results["breakfast"] = self.breakfast_agent.run_structured(
                    ingredients, time_constraint, meal_type=meal_type
                )
            except Exception as exc:
                results["breakfast"] = {
                    "section": "breakfast",
                    "status": "error",
                    "error": {"code": "agent_error", "message": str(exc)},
                }

        if "itinerary" in routed_agents:
            try:
                results["itinerary"] = self.itinerary_agent.run_structured(
                    location,
                    days=parsed.get("days", 2),
                    budget=parsed.get("budget", "moderate"),
                )
            except Exception as exc:
                results["itinerary"] = {
                    "section": "itinerary",
                    "status": "error",
                    "error": {"code": "agent_error", "message": str(exc)},
                }

        envelope = {
            "session_id": session_id or "",
            "intent": {
                "location":        location,
                "destination":     destination,
                "sections":        sections,
                "ingredients":     ingredients,
                "meal_type":       parsed.get("meal_type", "meal"),
                "time_constraint": time_constraint,
                "days":            parsed.get("days", 2),
                "budget":          parsed.get("budget", "moderate"),
            },
            "sections": results,
        }

        if session_id:
            self.session_manager.log_interaction(
                session_id,
                {"query": query, "structured": True, "sections_returned": list(results.keys())},
            )

        return envelope

    # ------------------------------------------------------------------
    # Tool discovery — Acceptance Criterion 2
    # ------------------------------------------------------------------
    def discover_tools(self) -> Dict[str, List[str]]:
        """Connect to all MCP servers and list their available tools."""
        return self.agentic_loop.discover_tools()

    # ------------------------------------------------------------------
    # Agentic run — Acceptance Criteria 3, 4, 5
    # ------------------------------------------------------------------
    def run_agentic(self, query: str, session_id: str | None = None) -> dict:
        """Execute the full ReAct agentic loop.

        Returns a dict with::

            {
                "session_id":        str,
                "intent":            dict,
                "sections":          dict,   # same shape as run_structured
                "loop_trace":        list,   # thought/action/observation steps
                "reflection":        dict,   # {changes_made, confirmations}
                "summary":           str,    # friendly NL summary
                "tools_discovered":  dict,   # server → [tool_names]
            }
        """
        from agents.agentic_loop import AgenticResult

        result: AgenticResult = self.agentic_loop.run(query, session_id=session_id or "")

        # Persist intent
        if session_id:
            self.session_manager.save_intent(session_id, result.intent)
            self.session_manager.log_interaction(
                session_id,
                {
                    "query": query,
                    "agentic": True,
                    "sections_returned": list(result.sections.keys()),
                    "reflection_changes": result.reflection.changes_made if result.reflection else [],
                },
            )

        # Serialise the trace
        trace_dicts = [
            {
                "step":        t.step,
                "thought":     t.thought,
                "action":      t.action,
                "action_args": t.action_args,
                "observation": t.observation,
                "duration_ms": t.duration_ms,
            }
            for t in result.trace
        ]

        return {
            "session_id":       result.session_id,
            "intent":           result.intent,
            "sections":         result.sections,
            "loop_trace":       trace_dicts,
            "reflection":       {
                "changes_made":  result.reflection.changes_made if result.reflection else [],
                "confirmations": result.reflection.confirmations if result.reflection else [],
            },
            "summary":          result.summary,
            "tools_discovered": result.tools_discovered,
            "briefing":         result.summary,  # compat with existing UI
        }

    # ------------------------------------------------------------------
    # Re-run a single section with an existing intent dict
    # ------------------------------------------------------------------
    def run_section(self, section: str, intent: dict) -> dict:
        """Re-invoke one agent using a saved intent.  Used by /refresh."""
        location        = intent.get("location", "")
        destination     = intent.get("destination", "")   # ← carries through on refresh
        ingredients     = intent.get("ingredients", [])
        meal_type       = intent.get("meal_type", "meal")
        time_constraint = intent.get("time_constraint", "15 min")

        meal_handler = lambda: self.breakfast_agent.run_structured(
            ingredients, time_constraint, meal_type=meal_type
        )

        dispatch = {
            "weather":   lambda: self.weather_agent.run_structured(location),
            "news":      lambda: self.news_agent.run_structured(),
            "commute":   lambda: self.commute_agent.run_structured(location, destination),
            "breakfast": meal_handler,
            "meal":      meal_handler,
            "meals":     meal_handler,
            "recipe":    meal_handler,
            "itinerary": lambda: self.itinerary_agent.run_structured(
                location,
                days=intent.get("days", 2),
                budget=intent.get("budget", "moderate"),
            ),
        }

        handler = dispatch.get(section)
        if handler is None:
            return {
                "section": section,
                "status": "error",
                "error": {"code": "unknown_section", "message": f"No agent for section '{section}'."},
            }
        try:
            return handler()
        except Exception as exc:
            return {
                "section": section,
                "status": "error",
                "error": {"code": "agent_error", "message": str(exc)},
            }
