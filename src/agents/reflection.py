"""Reflection engine — cross-checks gathered section data for consistency.

After the agentic loop has collected all section results, the reflection
engine scans for contradictions, safety issues, and optimisation
opportunities across sections and either **adjusts** an answer or
**confirms** it.

All rules are deterministic (no LLM required).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class ReflectionResult:
    """Outcome of the reflection pass."""
    changes_made: List[str] = field(default_factory=list)
    confirmations: List[str] = field(default_factory=list)


class ReflectionEngine:
    """Runs deterministic cross-section reflection rules."""

    def reflect(self, sections: Dict[str, Any], intent: Dict[str, Any]) -> ReflectionResult:
        """Run all reflection rules against the gathered data.

        Parameters
        ----------
        sections : dict
            Mapping of section name → structured result dict.
        intent : dict
            Parsed user intent with location, sections, etc.

        Returns
        -------
        ReflectionResult
            With lists of changes made and confirmations.
        """
        result = ReflectionResult()

        weather_data = self._extract_weather(sections)
        commute_data = self._extract_commute(sections)
        breakfast_data = self._extract_breakfast(sections)

        # ── Rule 1: Hot weather + outdoor commute ──────────────────────────
        if weather_data and commute_data:
            temp = weather_data.get("temp")
            mode = commute_data.get("recommended_mode", "drive")
            if temp is not None and temp >= 35 and mode in ("bike", "walk"):
                # Adjust: switch recommendation to drive
                commute_section = sections.get("commute", {})
                data = commute_section.get("data", {})
                old_mode = data.get("recommended_mode", mode)
                data["recommended_mode"] = "drive"
                data["mode_label"] = "Drive"
                alert_msg = (
                    f"⚠️ Extreme heat ({temp}°C) — switched recommendation "
                    f"from {old_mode} to drive for safety."
                )
                data.setdefault("alerts", []).insert(0, alert_msg)
                result.changes_made.append(
                    f"Changed commute mode from '{old_mode}' to 'drive' due to {temp}°C heat"
                )
            else:
                result.confirmations.append(
                    "Weather and commute mode are consistent"
                )

        # ── Rule 2: Cold weather + walking ─────────────────────────────────
        if weather_data and commute_data:
            temp = weather_data.get("temp")
            mode = commute_data.get("recommended_mode", "drive")
            if temp is not None and temp <= 2 and mode in ("walk", "bike"):
                commute_section = sections.get("commute", {})
                data = commute_section.get("data", {})
                alert_msg = (
                    f"🥶 Freezing conditions ({temp}°C) — bundle up warmly "
                    f"for {mode}ing, or consider driving."
                )
                data.setdefault("alerts", []).insert(0, alert_msg)
                result.changes_made.append(
                    f"Added cold weather alert for {mode}ing at {temp}°C"
                )

        # ── Rule 3: High UV + outdoor commute ─────────────────────────────
        if weather_data and commute_data:
            uv = weather_data.get("uv_index")
            # Always read current commute mode (never stale pre-override mode)
            mode = commute_data.get("recommended_mode", "drive")
            if uv is not None and isinstance(uv, (int, float)) and uv >= 8 and mode in ("bike", "walk"):
                commute_section = sections.get("commute", {})
                data = commute_section.get("data", {})
                alert_msg = (
                    f"☀️ UV index is very high ({uv}) — wear sunscreen and "
                    f"a hat for your {mode} commute."
                )
                data.setdefault("alerts", []).insert(0, alert_msg)
                result.changes_made.append(
                    f"Added UV warning (index {uv}) for {mode} commute"
                )

        # ── Rule 4: Long commute + slow meal prep ─────────────────────────
        if commute_data and breakfast_data:
            eta = commute_data.get("eta_minutes", 0)
            prep = breakfast_data.get("prep_time_minutes", 0)
            m_type = breakfast_data.get("meal_type", "meal")
            if eta >= 45 and prep >= 15:
                breakfast_section = sections.get("breakfast") or sections.get("meal", {})
                data = breakfast_section.get("data", {})
                data["reflection_note"] = (
                    f"💡 Your commute is {eta} min — consider a quicker "
                    f"10-minute {m_type} to save time."
                )
                result.changes_made.append(
                    f"Added time-saving note: {eta}-min commute + {prep}-min {m_type}"
                )
            else:
                result.confirmations.append(
                    f"Commute time and {m_type} prep are compatible"
                )

        # ── Rule 5: Weather + meal pairing ───────────────────────────
        if weather_data and breakfast_data:
            temp = weather_data.get("temp")
            recipe = (
                breakfast_data.get("recipe_name")
                or breakfast_data.get("name")
                or breakfast_data.get("title")
                or ""
            )
            m_type = breakfast_data.get("meal_type", "meal")
            recipe_lower = recipe.lower()

            hot_dish_keywords = (
                "hot", "stew", "porridge", "soup", "curry", "ramen",
                "casserole", "chili", "pot roast", "chowder", "goulash",
                "oatmeal", "pho", "broth", "fondue", "gumbo", "bisque", "tagine"
            )
            cold_dish_keywords = (
                "salad", "cold", "chilled", "smoothie", "gazpacho",
                "ice", "iced", "frozen", "poke", "ceviche", "acai", "açaí",
                "raw", "overnight oats"
            )

            if temp is not None and temp >= 30 and any(kw in recipe_lower for kw in hot_dish_keywords):
                breakfast_section = sections.get("breakfast") or sections.get("meal", {})
                data = breakfast_section.get("data", {})
                data["reflection_note"] = (
                    f"🌡️ It's {temp}°C outside — a cold or light {m_type} "
                    f"might be more refreshing."
                )
                result.changes_made.append(
                    f"Suggested lighter {m_type} due to {temp}°C heat"
                )
            elif temp is not None and temp <= 5 and any(kw in recipe_lower for kw in cold_dish_keywords):
                breakfast_section = sections.get("breakfast") or sections.get("meal", {})
                data = breakfast_section.get("data", {})
                data["reflection_note"] = (
                    f"❄️ It's {temp}°C outside — a warm, hearty {m_type} "
                    f"would keep you energized in the cold."
                )
                result.changes_made.append(
                    f"Suggested warm comfort {m_type} due to {temp}°C cold"
                )
            else:
                result.confirmations.append(
                    f"{m_type.capitalize()} choice suits the weather"
                )

        # ── Fallback: confirm everything if no changes ────────────────────
        if not result.changes_made and not result.confirmations:
            result.confirmations.append(
                "All sections reviewed — no adjustments needed"
            )

        return result

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_weather(sections: dict) -> dict | None:
        w = sections.get("weather", {})
        if w.get("status") != "success":
            return None
        return w.get("data", {})

    @staticmethod
    def _extract_commute(sections: dict) -> dict | None:
        c = sections.get("commute", {})
        if c.get("status") != "success":
            return None
        return c.get("data", {})

    @staticmethod
    def _extract_breakfast(sections: dict) -> dict | None:
        b = sections.get("breakfast") or sections.get("meal", {})
        if b.get("status") != "success":
            return None
        return b.get("data", {})
