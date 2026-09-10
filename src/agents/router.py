from __future__ import annotations

from typing import Any, Dict, List, Optional
from services.llm_client import LLMClient


class Router:
    """Simple intent router that directs requests to specialist agents."""

    def __init__(self) -> None:
        self.routes: Dict[str, List[str]] = {
            "weather": ["weather"],
            "uv": ["weather"],
            "news": ["news"],
            "commute": ["commute"],
            "breakfast": ["breakfast"],
            "meal": ["breakfast"],
            "meals": ["breakfast"],
            "recipe": ["breakfast"],
            "lunch": ["breakfast"],
            "dinner": ["breakfast"],
            "snack": ["breakfast"],
            "itinerary": ["itinerary"],
        }

    def route(self, sections: List[str]) -> List[str]:
        selected: List[str] = []
        for section in sections:
            selected.extend(self.routes.get(section, []))
        return list(dict.fromkeys(selected))


class LLMRouter(Router):
    """Genuinely LLM-driven router that uses an LLM to select tools/sections based on user query and discovered tool manifests."""

    def __init__(self, llm_client: Optional[LLMClient] = None) -> None:
        super().__init__()
        self.llm_client = llm_client or LLMClient()

    def route_query(
        self,
        query: str,
        discovered_tools: Optional[Dict[str, List[str]]] = None,
        fallback_sections: Optional[List[str]] = None,
    ) -> List[str]:
        """Route user query using LLM if available, otherwise fall back to deterministic router."""
        if self.llm_client and self.llm_client.is_available():
            try:
                tools_manifest = discovered_tools or {
                    "weather": ["get_weather"],
                    "news": ["get_headlines"],
                    "commute": ["get_commute_route"],
                    "recipe": ["get_recipe"],
                    "itinerary": ["get_itinerary"],
                    "gmail": ["send_email_briefing"],
                }
                res = self.llm_client.route_intent(query, tools_manifest)
                sections = res.get("sections", [])
                if sections and isinstance(sections, list):
                    return self.route(sections)
            except Exception:
                pass

        if fallback_sections is not None:
            return self.route(fallback_sections)
        return self.route([])

