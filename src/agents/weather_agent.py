"""WeatherAgent — wraps WeatherTool and shapes the output for UI cards.

run()           → plain text  (CLI / legacy)
run_structured() → typed dict  (web API §3.1)
"""
from __future__ import annotations

from mcp_tools.weather_tools import WeatherTool

# WHO UV risk thresholds
_UV_LABELS = [
    (3,  "Low — no protection needed"),
    (6,  "Moderate — wear sunscreen"),
    (8,  "High — seek shade midday"),
    (11, "Very High — stay indoors at peak"),
]


def _uv_label(uv) -> str:
    try:
        v = float(uv)
    except (TypeError, ValueError):
        return "Unknown"
    for threshold, label in _UV_LABELS:
        if v < threshold:
            return label
    return "Extreme — avoid outdoor exposure"


def _parse_temp(temp_str: str | float | None) -> float | None:
    """Extract a numeric °C value from various representations."""
    if temp_str is None:
        return None
    if isinstance(temp_str, (int, float)):
        return float(temp_str)
    try:
        return float(str(temp_str).replace("°C", "").replace("°F", "").strip())
    except ValueError:
        return None


def _derive_condition(temp_c: float | None) -> str:
    if temp_c is None:
        return "Partly Cloudy"
    if temp_c >= 35:
        return "Very Hot"
    if temp_c >= 28:
        return "Hot & Sunny"
    if temp_c >= 20:
        return "Warm & Clear"
    if temp_c >= 12:
        return "Mild"
    if temp_c >= 4:
        return "Cool"
    return "Cold"


class WeatherAgent:
    def __init__(self) -> None:
        self.tool = WeatherTool()

    # ── CLI / legacy ───────────────────────────────────────────────────────
    def run(self, location: str) -> str:
        data = self.tool.get_weather(location)
        return (
            f"## Weather\n"
            f"- Location: {location}\n"
            f"- Temperature: {data['temperature']}\n"
            f"- UV Index: {data['uv_index']}"
        )

    # ── Structured (web API §3.1) ──────────────────────────────────────────
    def run_structured(self, location: str) -> dict:
        raw      = self.tool.get_weather(location)
        temp_val = _parse_temp(raw.get("temperature"))
        uv_raw   = raw.get("uv_index", "unavailable")

        try:
            uv_val = round(float(uv_raw), 1)
        except (TypeError, ValueError):
            uv_val = None

        condition = _derive_condition(temp_val)

        # Real hourly data from the tool; synthetic fallback only if empty
        real_hourly: list[dict] = raw.get("hourly", [])
        if real_hourly:
            hourly = [
                {
                    "time":     h["time"],
                    "temp":     h["temp"],
                    "uv_index": h["uv_index"],
                }
                for h in real_hourly
            ]
        else:
            # Fallback: generate 5-point synthetic curve if tool returned nothing
            base = temp_val or 20.0
            uv   = uv_val   or 4.0
            hourly = [
                {"time": "07:00", "temp": round(base - 3, 1), "uv_index": 1.0},
                {"time": "10:00", "temp": round(base + 1, 1), "uv_index": round(uv * 0.7, 1)},
                {"time": "13:00", "temp": round(base + 4, 1), "uv_index": uv},
                {"time": "16:00", "temp": round(base + 2, 1), "uv_index": round(uv * 0.5, 1)},
                {"time": "19:00", "temp": round(base - 1, 1), "uv_index": 0.5},
            ]

        return {
            "section": "weather",
            "status":  "success",
            "data": {
                "temp":      temp_val if temp_val is not None else raw.get("temperature"),
                "temp_unit": "C",
                "condition": condition,
                "high":      round(max(h["temp"] for h in hourly if h["temp"] is not None), 1)
                             if hourly else "n/a",
                "low":       round(min(h["temp"] for h in hourly if h["temp"] is not None), 1)
                             if hourly else "n/a",
                "uv_index":  uv_val if uv_val is not None else uv_raw,
                "uv_label":  _uv_label(uv_val),
                "source":    raw.get("source", "unknown"),
                "lat":       raw.get("lat"),
                "lon":       raw.get("lon"),
                "hourly":    hourly,
            },
        }
