"""ItineraryAgent — specialist agent for multi-day travel planning."""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from mcp_tools.itinerary_tools import get_itinerary, mcp as itinerary_mcp_server


class ItineraryAgent:
    """Specialist agent for generating travel itineraries."""

    def __init__(self) -> None:
        self.tool = itinerary_mcp_server

    def run(
        self,
        location: str,
        days: int = 2,
        budget: str = "moderate",
        interests: Optional[List[str]] = None,
    ) -> str:
        """Return plain-text formatted itinerary for CLI output."""
        data = get_itinerary(location, days, budget, interests)
        lines = [
            f"## Travel Itinerary: {data['location']} ({data['days_count']} Days)",
            f"Budget: {data['budget'].title()} ({data['estimated_cost']})",
            "",
        ]
        for day in data.get("days", []):
            lines.append(f"### Day {day['day_number']}: {day['theme']}")
            lines.append(f"- Morning: {day['morning']['activity']} ({day['morning']['location']})")
            lines.append(f"- Afternoon: {day['afternoon']['activity']} ({day['afternoon']['location']})")
            lines.append(f"- Evening: {day['evening']['activity']} ({day['evening']['location']})")
            lines.append(f"- Dining: Lunch: {day['dining']['lunch']} | Dinner: {day['dining']['dinner']}")
            lines.append("")

        if data.get("travel_tips"):
            lines.append("### Travel Tips:")
            for tip in data["travel_tips"]:
                lines.append(f"- {tip}")

        return "\n".join(lines)

    def run_structured(
        self,
        location: str,
        days: int = 2,
        budget: str = "moderate",
        interests: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Return typed dict matching structured API contract shape."""
        try:
            data = get_itinerary(location, days, budget, interests)
            return {
                "section": "itinerary",
                "status": "success",
                "data": data,
            }
        except Exception as exc:
            return {
                "section": "itinerary",
                "status": "error",
                "error": {"code": "agent_error", "message": str(exc)},
            }
