"""Agentic ReAct loop — iterative tool-calling with thought/action/observation.

Implements the perceive → plan → act → observe → decide cycle required by
the acceptance criteria.  All reasoning is deterministic (no LLM needed).

Usage::

    loop = AgenticLoop(server_registry, parser)
    result = loop.run("Weather and commute from Chicago with eggs")
    # result.sections   → {weather: {...}, commute: {...}, breakfast: {...}}
    # result.trace      → [{step, thought, action, observation}, ...]
    # result.reflection → ReflectionResult
    # result.summary    → friendly natural-language string
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from agents.mcp_agent import MCPAgent
from agents.reflection import ReflectionEngine, ReflectionResult
from agents.response_synthesizer import synthesize_response
from mcp_tools.server_registry import ServerRegistry
from nlp.query_parser import QueryParser
from agents.router import Router


# ── Data classes ───────────────────────────────────────────────────────────

@dataclass
class TraceStep:
    """One iteration of the agentic loop."""
    step: int
    thought: str
    action: str
    action_args: Dict[str, Any]
    observation: str
    duration_ms: int = 0


@dataclass
class AgenticResult:
    """Final output of the agentic loop."""
    session_id: str
    intent: Dict[str, Any]
    sections: Dict[str, Any]
    trace: List[TraceStep]
    reflection: Optional[ReflectionResult] = None
    summary: str = ""
    tools_discovered: Dict[str, List[str]] = field(default_factory=dict)


# ── Tool-to-section mapping ───────────────────────────────────────────────

# Maps a requested section to the (server_name, tool_name, arg_builder) needed
# to fulfil it.  arg_builder receives the parsed intent and returns kwargs.

def _weather_args(intent: dict) -> dict:
    return {"location": intent.get("location", "")}


def _news_args(intent: dict) -> dict:
    return {"location": intent.get("location", "")}


def _commute_args(intent: dict) -> dict:
    return {
        "location": intent.get("location", ""),
        "destination": intent.get("destination", ""),
        "mode": "drive",
    }


def _recipe_args(intent: dict) -> dict:
    return {
        "ingredients": intent.get("ingredients", []),
        "time_constraint": intent.get("time_constraint", "15 min"),
        "meal_type": intent.get("meal_type", "meal"),
    }


def _itinerary_args(intent: dict) -> dict:
    return {
        "location": intent.get("location", ""),
        "days": intent.get("days", 2),
        "budget": intent.get("budget", "moderate"),
        "interests": ["Sightseeing", "Food", "Local Culture"],
    }


def _email_args(intent: dict) -> dict:
    return {
        "to_email": intent.get("to_email", "traveler@example.com"),
        "subject": f"Travel Briefing for {intent.get('location', '')}",
        "body_html": f"<p>Briefing for {intent.get('location', '')}</p>",
    }


_SECTION_TOOL_MAP: Dict[str, dict] = {
    "weather":   {"server": "weather",   "tool": "get_weather",        "args": _weather_args},
    "news":      {"server": "news",      "tool": "get_headlines",      "args": _news_args},
    "commute":   {"server": "commute",   "tool": "get_commute_route",  "args": _commute_args},
    "breakfast": {"server": "recipe",    "tool": "get_recipe",         "args": _recipe_args},
    "itinerary": {"server": "itinerary", "tool": "get_itinerary",      "args": _itinerary_args},
    "email":     {"server": "gmail",     "tool": "send_email_briefing","args": _email_args},
}

# Maps tool outputs to the structured section format the agents produce.
# We re-use the same shaping logic the specialist agents use.

from agents.weather_agent import WeatherAgent
from agents.news_agent import NewsAgent
from agents.commute_agent import CommuteAgent
from agents.breakfast_agent import BreakfastAgent


def _shape_weather(raw: dict) -> dict:
    """Shape raw weather tool output into the structured card format."""
    agent = WeatherAgent.__new__(WeatherAgent)
    # Temporarily wire the raw data through the agent's shaping logic
    from mcp_tools.weather_tools import WeatherTool
    agent.tool = WeatherTool()
    # We already have raw data; re-shape it using the agent's helper functions
    from agents.weather_agent import _parse_temp, _uv_label, _derive_condition
    temp_val = _parse_temp(raw.get("temperature"))
    uv_raw = raw.get("uv_index", "unavailable")
    try:
        uv_val = round(float(uv_raw), 1)
    except (TypeError, ValueError):
        uv_val = None

    condition = _derive_condition(temp_val)
    real_hourly = raw.get("hourly", [])
    if real_hourly:
        hourly = [{"time": h["time"], "temp": h["temp"], "uv_index": h["uv_index"]} for h in real_hourly]
    else:
        base = temp_val or 20.0
        uv = uv_val or 4.0
        hourly = [
            {"time": "07:00", "temp": round(base - 3, 1), "uv_index": 1.0},
            {"time": "10:00", "temp": round(base + 1, 1), "uv_index": round(uv * 0.7, 1)},
            {"time": "13:00", "temp": round(base + 4, 1), "uv_index": uv},
            {"time": "16:00", "temp": round(base + 2, 1), "uv_index": round(uv * 0.5, 1)},
            {"time": "19:00", "temp": round(base - 1, 1), "uv_index": 0.5},
        ]

    return {
        "section": "weather",
        "status": "success",
        "data": {
            "temp": temp_val if temp_val is not None else raw.get("temperature"),
            "temp_unit": "C",
            "condition": condition,
            "high": round(max(h["temp"] for h in hourly if h["temp"] is not None), 1) if hourly else "n/a",
            "low": round(min(h["temp"] for h in hourly if h["temp"] is not None), 1) if hourly else "n/a",
            "uv_index": uv_val if uv_val is not None else uv_raw,
            "uv_label": _uv_label(uv_val),
            "source": raw.get("source", "unknown"),
            "lat": raw.get("lat"),
            "lon": raw.get("lon"),
            "hourly": hourly,
        },
    }


def _shape_news(raw: list) -> dict:
    """Shape raw headlines list into the structured card format."""
    headlines = []
    for item in raw[:5]:
        if isinstance(item, dict):
            headlines.append({
                "title": (item.get("title") or "").strip(),
                "source": item.get("source") or "News",
                "url": item.get("url"),
                "timestamp": item.get("published_at") or "",
            })
        else:
            title = str(item).strip()
            headlines.append({"title": title, "source": "News", "url": None, "timestamp": ""})
    headlines = [h for h in headlines if h["title"]]
    return {
        "section": "news",
        "status": "success" if headlines else "error",
        "data": {"headlines": headlines},
    }


def _shape_commute(raw: dict) -> dict:
    """Shape raw commute tool output into the structured card format."""
    _MODE_LABELS = {"drive": "Drive", "transit": "Transit", "bike": "Bike", "walk": "Walk"}
    mode = raw.get("recommended_mode", "drive")
    alternates = [
        {
            "mode": alt.get("mode", ""),
            "eta_minutes": alt.get("eta_minutes", 0),
            "distance_km": alt.get("distance_km", 0.0),
            "polyline": alt.get("polyline", []),
        }
        for alt in raw.get("alternates", [])
    ]
    return {
        "section": "commute",
        "status": "success",
        "data": {
            "recommended_mode": mode,
            "eta_minutes": raw.get("eta_minutes", 28),
            "alerts": raw.get("alerts", []),
            "alternates": alternates,
            "distance_km": raw.get("distance_km", 0.0),
            "polyline": raw.get("polyline", []),
            "origin": raw.get("origin", {}),
            "dest": raw.get("dest", {}),
            "source": raw.get("source", "advisory"),
            "mode_label": _MODE_LABELS.get(mode, mode.capitalize()),
        },
    }


def _shape_breakfast(raw: dict) -> dict:
    """Shape raw recipe tool output into the structured card format."""
    import re
    def _parse_minutes(time_val):
        if isinstance(time_val, int):
            return time_val
        m = re.search(r"(\d+)", str(time_val))
        return int(m.group(1)) if m else 15

    name = raw.get("name") or raw.get("recipe_name") or "Quick meal"
    used = raw.get("ingredients_used") or raw.get("ingredients") or ["eggs"]
    prep = _parse_minutes(raw.get("prep_time_minutes") or raw.get("time", "15 min"))
    cook = _parse_minutes(raw.get("cook_time_minutes", prep))
    total = raw.get("total_time_minutes") or (prep + cook)
    steps = raw.get("steps") or [
        f"Gather your ingredients: {', '.join(str(i) for i in used)}.",
        "Season lightly with salt, pepper, and olive oil.",
        f"Cook the {name} over medium heat until tender and fragrant.",
        "Plate and serve immediately.",
    ]

    return {
        "section": "breakfast",
        "status": "success",
        "data": {
            "name": name,
            "recipe_name": name,
            "meal_type": raw.get("meal_type", "meal"),
            "prep_time_minutes": prep,
            "cook_time_minutes": cook,
            "total_time_minutes": total,
            "ingredients_used": used,
            "pantry_staples": raw.get("pantry_staples", []),
            "steps": steps,
            "nutrition_highlights": raw.get("nutrition_highlights", ""),
            "chef_tip": raw.get("chef_tip", ""),
            "alternates": raw.get("alternates", []),
            "category": raw.get("category", ""),
            "area": raw.get("area", ""),
            "thumbnail": raw.get("thumbnail", ""),
        },
    }


def _shape_itinerary(raw: dict) -> dict:
    """Shape itinerary output into section format."""
    return {
        "section": "itinerary",
        "status": "success",
        "data": raw,
    }


def _shape_email(raw: dict) -> dict:
    """Shape email tool output into section format."""
    return {
        "section": "email",
        "status": "success",
        "data": raw,
    }


_SECTION_SHAPERS = {
    "weather": _shape_weather,
    "news": _shape_news,
    "commute": _shape_commute,
    "breakfast": _shape_breakfast,
    "itinerary": _shape_itinerary,
    "email": _shape_email,
}


from services.llm_client import LLMClient


def _parse_action_target(action_str: str) -> tuple[str, str, str]:
    """Parse 'server.tool' or 'tool' or 'server' into (server_name, tool_name, section_name)."""
    clean_action = action_str.strip()
    if "." in clean_action:
        server_name, tool_name = clean_action.split(".", 1)
    else:
        server_name = clean_action
        tool_name = clean_action
        for sec, meta in _SECTION_TOOL_MAP.items():
            if meta["server"] == clean_action or meta["tool"] == clean_action or sec == clean_action:
                server_name = meta["server"]
                tool_name = meta["tool"]
                break

    section_name = "unknown"
    for sec, meta in _SECTION_TOOL_MAP.items():
        if meta["server"] == server_name or meta["tool"] == tool_name:
            section_name = sec
            break
    if section_name == "unknown":
        section_name = server_name

    return server_name, tool_name, section_name


def _build_observation_summary(section: str, shaped: dict) -> str:
    """Build concise observation text for trace steps."""
    data = shaped.get("data", {}) if isinstance(shaped, dict) else {}
    if section == "weather":
        return (
            f"Got weather: {data.get('temp')}°C, "
            f"UV {data.get('uv_index')}, "
            f"condition: {data.get('condition')}."
        )
    elif section == "news":
        count = len(data.get("headlines", []))
        return f"Got {count} headlines."
    elif section == "commute":
        return (
            f"Got commute: {data.get('eta_minutes')} min "
            f"by {data.get('recommended_mode')}, "
            f"{data.get('distance_km')} km."
        )
    elif section == "breakfast":
        m_type = data.get('meal_type', 'meal')
        return (
            f"Got {m_type} recipe: {data.get('recipe_name')} "
            f"({data.get('prep_time_minutes')} min prep)."
        )
    elif section == "itinerary":
        loc = data.get('location', '')
        days_c = data.get('days_count', 2)
        return f"Generated {days_c}-day itinerary for {loc}."
    elif section == "email":
        status = data.get('status', 'ok')
        return f"Email tool status: {status}."
    return f"Got result for {section}."


# ── Agentic Loop ───────────────────────────────────────────────────────────

MAX_ITERATIONS = 8  # safety net


class AgenticLoop:
    """ReAct-style agentic loop over MCP tool servers."""

    def __init__(
        self,
        server_registry: Union[ServerRegistry, Any],
        parser: QueryParser | None = None,
        router: Router | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self.server_registry = server_registry
        self.parser = parser or QueryParser()
        self.router = router or Router()
        self.llm_client = llm_client or LLMClient()
        self.reflection_engine = ReflectionEngine()

        # Build MCP agents for each server (using RealMCPServer or RemoteMCPClient)
        self._agents: Dict[str, MCPAgent] = {}
        if hasattr(server_registry, "list_servers"):
            for name in server_registry.list_servers():
                client_or_server = (
                    server_registry.get_client(name)
                    if hasattr(server_registry, "get_client")
                    else server_registry.get_server(name)
                )
                self._agents[name] = MCPAgent(name, client_or_server)

    # ── Discovery ──────────────────────────────────────────────────────────

    def discover_tools(self) -> Dict[str, List[str]]:
        """Connect to all servers and list their tools."""
        discovered: Dict[str, List[str]] = {}
        for name, agent in self._agents.items():
            agent.connect()
            discovered[name] = agent.list_tools()
        return discovered

    # ── Main loop ──────────────────────────────────────────────────────────

    def run(self, query: str, session_id: str = "") -> AgenticResult:
        """Execute the full agentic loop for a user query.

        Steps:
        1. PERCEIVE  — parse query, discover tools
        2. PLAN      — decide which sections/tools to call
        3. ACT       — invoke tool
        4. OBSERVE   — inspect result
        5. DECIDE    — LLM or rule-based stop check
        6. REFLECT   — cross-check data
        7. RESPOND   — synthesize summary
        """

        # ── Step 1: PERCEIVE ───────────────────────────────────────────────
        try:
            from services.telemetry import telemetry
            telemetry.agent(f"PERCEIVE: parsing query '{query}'", trace_id=session_id, agent_name="agentic_loop")
        except Exception:
            telemetry = None

        parsed = self.parser.parse(query)
        intent = {
            "location": parsed.get("location", ""),
            "destination": parsed.get("destination", ""),
            "sections": parsed.get("sections", []),
            "ingredients": parsed.get("ingredients", []),
            "meal_type": parsed.get("meal_type", "meal"),
            "time_constraint": parsed.get("time_constraint", "15 min"),
            "days": parsed.get("days", 2),
            "budget": parsed.get("budget", "moderate"),
        }

        # Discover available tools from MCP servers
        tools_discovered = self.discover_tools()
        fulfilled: Dict[str, Any] = {}
        trace: List[TraceStep] = []
        step_num = 0

        # Check if LLM-driven loop can be used
        use_llm_loop = bool(self.llm_client and self.llm_client.is_available())

        if use_llm_loop:
            # ── LLM-Driven ACT → OBSERVE → DECIDE Loop ──────────────────────
            if telemetry:
                telemetry.agent("PLAN: using LLM-driven routing and tool selection", trace_id=session_id, agent_name="agentic_loop")

            try:
                while step_num < MAX_ITERATIONS:
                    trace_history_dicts = [
                        {
                            "step": t.step,
                            "thought": t.thought,
                            "action": t.action,
                            "action_args": t.action_args,
                            "observation": t.observation,
                        }
                        for t in trace
                    ]

                    decision = self.llm_client.select_next_action(
                        query=query,
                        tools_manifest=tools_discovered,
                        trace_history=trace_history_dicts,
                    )

                    thought = decision.get("thought", "")
                    action = decision.get("action", "finish")
                    llm_args = decision.get("action_args", {})

                    if action.lower() in ("finish", "complete", "done", "stop") or action == "finish_complete":
                        step_num += 1
                        trace.append(TraceStep(
                            step=step_num,
                            thought=thought or "All user requests fulfilled.",
                            action="finish_complete",
                            action_args={},
                            observation=f"Successfully gathered {len(fulfilled)} sections: {list(fulfilled.keys())}.",
                        ))
                        break

                    server_name, tool_name, section = _parse_action_target(action)
                    step_num += 1

                    default_arg_fn = _SECTION_TOOL_MAP.get(section, {}).get("args")
                    base_args = default_arg_fn(intent) if default_arg_fn else {}
                    tool_args = {**base_args, **llm_args}

                    action_label = f"{server_name}.{tool_name}"
                    t0 = time.perf_counter()
                    try:
                        agent = self._agents.get(server_name)
                        if not agent:
                            obs = f"Server '{server_name}' not found."
                            elapsed_ms = 0
                        else:
                            raw_result = agent.invoke(tool_name, **tool_args)

                            shaper = _SECTION_SHAPERS.get(section)
                            if shaper:
                                shaped = shaper(raw_result)
                            else:
                                shaped = {"section": section, "status": "success", "data": raw_result}

                            elapsed_ms = int((time.perf_counter() - t0) * 1000)
                            obs = _build_observation_summary(section, shaped)
                            if telemetry:
                                telemetry.tool(server_name, tool_name, elapsed_ms, status="OK", trace_id=session_id)
                            fulfilled[section] = shaped

                    except Exception as exc:
                        elapsed_ms = int((time.perf_counter() - t0) * 1000)
                        obs = f"Error calling {action_label}: {exc}"
                        if telemetry:
                            telemetry.tool(server_name, tool_name, elapsed_ms, status="ERROR", trace_id=session_id, error=str(exc))
                        fulfilled[section] = {
                            "section": section,
                            "status": "error",
                            "error": {"code": "tool_error", "message": str(exc)},
                        }

                    trace.append(TraceStep(
                        step=step_num,
                        thought=thought,
                        action=action_label,
                        action_args=tool_args,
                        observation=obs,
                        duration_ms=elapsed_ms,
                    ))
            except Exception as exc:
                if telemetry:
                    telemetry.error("AgenticLoop", f"LLM select_next_action failed: {exc}. Falling back to deterministic loop.")
                use_llm_loop = False
                fulfilled = {}
                trace = []
                step_num = 0

        if not use_llm_loop:

            # ── Deterministic Rule-Based Fallback Loop ───────────────────────

            routed_sections = self.router.route(intent["sections"])
            if telemetry:
                telemetry.agent(f"PLAN: deterministic fallback routed sections -> {routed_sections}", trace_id=session_id, agent_name="router")
            pending = list(routed_sections)

            while pending and step_num < MAX_ITERATIONS:
                section = pending.pop(0)
                step_num += 1

                mapping = _SECTION_TOOL_MAP.get(section)
                if not mapping:
                    trace.append(TraceStep(
                        step=step_num,
                        thought=f"Section '{section}' has no tool mapping — skipping.",
                        action="skip",
                        action_args={},
                        observation=f"No tool available for '{section}'.",
                    ))
                    continue

                server_name = mapping["server"]
                tool_name = mapping["tool"]
                arg_builder = mapping["args"]
                tool_args = arg_builder(intent)

                available_tools = tools_discovered.get(server_name, [])
                thought = (
                    f"I need {section} data. Server '{server_name}' exposes "
                    f"{available_tools}. I'll call '{tool_name}' with "
                    f"{tool_args}."
                )

                action = f"{server_name}.{tool_name}"
                t0 = time.perf_counter()
                try:
                    agent = self._agents[server_name]
                    raw_result = agent.invoke(tool_name, **tool_args)

                    shaper = _SECTION_SHAPERS.get(section)
                    if shaper:
                        shaped = shaper(raw_result)
                    else:
                        shaped = {"section": section, "status": "success", "data": raw_result}

                    elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    obs = _build_observation_summary(section, shaped)

                    if telemetry:
                        telemetry.tool(server_name, tool_name, elapsed_ms, status="OK", trace_id=session_id)

                    fulfilled[section] = shaped

                except Exception as exc:
                    elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    obs = f"Error calling {action}: {exc}"
                    if telemetry:
                        telemetry.tool(server_name, tool_name, elapsed_ms, status="ERROR", trace_id=session_id, error=str(exc))
                    fulfilled[section] = {
                        "section": section,
                        "status": "error",
                        "error": {"code": "tool_error", "message": str(exc)},
                    }

                trace.append(TraceStep(
                    step=step_num,
                    thought=thought,
                    action=action,
                    action_args=tool_args,
                    observation=obs,
                    duration_ms=elapsed_ms,
                ))

            # DECIDE check completeness for deterministic loop
            missing = [s for s in routed_sections if s not in fulfilled]
            if missing:
                step_num += 1
                trace.append(TraceStep(
                    step=step_num,
                    thought=f"Sections still missing: {missing}. Max iterations reached.",
                    action="finish_incomplete",
                    action_args={},
                    observation=f"Returning {len(fulfilled)} of {len(routed_sections)} sections.",
                ))
            else:
                step_num += 1
                trace.append(TraceStep(
                    step=step_num,
                    thought="All requested sections fulfilled. Proceeding to reflection.",
                    action="finish_complete",
                    action_args={},
                    observation=f"Successfully gathered {len(fulfilled)} sections: {list(fulfilled.keys())}.",
                ))


        # ── Step 6: REFLECT ────────────────────────────────────────────────
        reflection = self.reflection_engine.reflect(fulfilled, intent)

        step_num += 1
        if reflection.changes_made:
            refl_obs = f"Reflection made {len(reflection.changes_made)} change(s): {'; '.join(reflection.changes_made)}"
        else:
            refl_obs = f"Reflection confirmed all answers: {'; '.join(reflection.confirmations)}"

        if telemetry:
            telemetry.reflection(refl_obs, trace_id=session_id, overrides_count=len(reflection.changes_made))

        trace.append(TraceStep(
            step=step_num,
            thought="Reviewing all gathered data for cross-section consistency.",
            action="reflect",
            action_args={},
            observation=refl_obs,
        ))

        # ── Step 7: RESPOND ────────────────────────────────────────────────
        summary = synthesize_response(fulfilled, intent, reflection)

        step_num += 1
        trace.append(TraceStep(
            step=step_num,
            thought="Composing a concise, friendly summary that references fetched data.",
            action="synthesize_response",
            action_args={},
            observation=f"Generated {len(summary)}-character summary.",
        ))

        if telemetry:
            telemetry.agent(f"RESPOND: Completed ReAct briefing in {step_num} steps", trace_id=session_id, agent_name="agentic_loop")
            telemetry.record_trace({
                "session_id": session_id,
                "query": query,
                "intent": intent,
                "sections_count": len(fulfilled),
                "total_steps": len(trace),
                "steps": [
                    {
                        "step": s.step,
                        "thought": s.thought,
                        "action": s.action,
                        "action_args": s.action_args,
                        "observation": s.observation,
                        "duration_ms": s.duration_ms,
                    }
                    for s in trace
                ],
                "reflection_changes": reflection.changes_made if reflection else [],
            })

        return AgenticResult(
            session_id=session_id,
            intent=intent,
            sections=fulfilled,
            trace=trace,
            reflection=reflection,
            summary=summary,
            tools_discovered=tools_discovered,
        )
