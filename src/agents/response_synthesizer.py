"""Response synthesizer — generates a concise, friendly natural-language summary.

Takes the gathered section data, intent, and reflection result, then
produces a human-readable briefing that **references actual fetched data**
(temperatures, ETAs, recipe names, headlines).

All generation is template-based — no LLM required.
"""
from __future__ import annotations

from typing import Any, Dict

from agents.reflection import ReflectionResult


def _greeting() -> str:
    """Return a time-appropriate greeting."""
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def _weather_segment(data: dict) -> str:
    """Build the weather portion of the summary."""
    temp = data.get("temp")
    condition = data.get("condition", "")
    uv = data.get("uv_index")
    uv_label = data.get("uv_label", "")
    high = data.get("high", "")
    low = data.get("low", "")

    parts = []
    if temp is not None:
        parts.append(f"It's currently {temp}°C ({condition.lower()})")
    if high and low and high != "n/a":
        parts.append(f"with a high of {high}°C and a low of {low}°C")
    if uv is not None and isinstance(uv, (int, float)):
        parts.append(f"UV index is {uv} — {uv_label.lower()}")

    return ". ".join(parts) + "." if parts else ""


def _news_segment(data: dict) -> str:
    """Build the news portion of the summary."""
    headlines = data.get("headlines", [])
    if not headlines:
        return ""
    titles = [h.get("title", "") for h in headlines[:3] if h.get("title")]
    if not titles:
        return ""
    if len(titles) == 1:
        return f"Top headline: \"{titles[0]}\"."
    return "Today's top stories: " + "; ".join(f"\"{t}\"" for t in titles) + "."


def _commute_segment(data: dict) -> str:
    """Build the commute portion of the summary."""
    mode = data.get("mode_label") or data.get("recommended_mode", "drive")
    eta = data.get("eta_minutes")
    dist = data.get("distance_km")
    dest = data.get("dest", {})
    dest_label = dest.get("label", "your destination")
    source = data.get("source", "")
    alerts = data.get("alerts", [])

    parts = []
    if eta is not None:
        segment = f"Your {mode.lower()} to {dest_label} is about {eta} minutes"
        if dist:
            segment += f" ({dist} km)"
        parts.append(segment)

    if source == "tomtom":
        parts.append("based on live traffic data")
    elif source == "ors":
        parts.append("based on routing data")

    text = ", ".join(parts) + "." if parts else ""

    # Include the first alert if any
    if alerts:
        # Skip reflection-injected alerts (they'll appear in reflection notes)
        real_alerts = [a for a in alerts if not a.startswith(("⚠️", "🥶", "☀️"))]
        if real_alerts:
            text += f" Heads up: {real_alerts[0]}"

    return text


def _breakfast_segment(data: dict) -> str:
    """Build the meal/recipe portion of the summary."""
    name = data.get("name") or data.get("recipe_name", "")
    m_type = (data.get("meal_type") or "meal").lower()
    prep = data.get("prep_time_minutes")
    ingredients = data.get("ingredients_used") or data.get("ingredients", [])
    chef_tip = data.get("chef_tip", "")
    reflection_note = data.get("reflection_note", "")

    parts = []
    if name:
        segment = f"For {m_type}, try {name}"
        if prep:
            segment += f" ({prep}-minute prep)"
        parts.append(segment)

    if ingredients:
        ing_str = ", ".join(str(i) for i in ingredients[:4])
        if len(ingredients) > 4:
            ing_str += f" and {len(ingredients) - 4} more"
        parts.append(f"featuring {ing_str}")

    text = " — ".join(parts) + "." if parts else ""

    if reflection_note:
        text += f" {reflection_note}"
    elif chef_tip and len(chef_tip) < 90:
        text += f" Tip: {chef_tip}"

    return text


def _itinerary_segment(data: dict) -> str:
    """Build the itinerary portion of the summary."""
    loc = data.get("location", "your destination")
    days = data.get("days_count") or len(data.get("days", []))
    cost = data.get("estimated_cost", "")
    return f"Here is your {days}-day travel itinerary for {loc} ({cost})."


def synthesize_response(
    sections: Dict[str, Any],
    intent: Dict[str, Any],
    reflection: ReflectionResult,
) -> str:
    """Generate a concise, friendly summary referencing fetched data.

    Parameters
    ----------
    sections : dict
        Section name → structured result dict.
    intent : dict
        Parsed user intent.
    reflection : ReflectionResult
        Output of the reflection pass.

    Returns
    -------
    str
        A natural-language summary suitable for display to the user.
    """
    location = intent.get("location", "your area")
    greeting = _greeting()

    parts = [f"{greeting}! Here's your briefing for {location}. "]

    # Weather
    w = sections.get("weather", {})
    if w.get("status") == "success":
        seg = _weather_segment(w["data"])
        if seg:
            parts.append(f"🌤️ {seg} ")

    # News
    n = sections.get("news", {})
    if n.get("status") == "success":
        seg = _news_segment(n["data"])
        if seg:
            parts.append(f"📰 {seg} ")

    # Commute
    c = sections.get("commute", {})
    if c.get("status") == "success":
        seg = _commute_segment(c["data"])
        if seg:
            parts.append(f"🚗 {seg} ")

    # Meal (Breakfast / Lunch / Dinner)
    b = sections.get("breakfast") or sections.get("meal", {})
    if b.get("status") == "success":
        seg = _breakfast_segment(b["data"])
        if seg:
            m_type = (b["data"].get("meal_type") or "meal").lower()
            icon_map = {
                "breakfast": "🍳",
                "lunch": "🥗",
                "dinner": "🍲",
                "snack": "🥪",
                "meal": "🍽️",
            }
            icon = icon_map.get(m_type, "🍽️")
            parts.append(f"{icon} {seg} ")

    # Itinerary
    it = sections.get("itinerary", {})
    if it.get("status") == "success":
        seg = _itinerary_segment(it["data"])
        if seg:
            parts.append(f"🗺️ {seg} ")

    # Reflection notes
    if reflection.changes_made:
        notes = " ".join(f"📝 {c}" for c in reflection.changes_made)
        parts.append(notes)

    return "".join(parts).strip()
