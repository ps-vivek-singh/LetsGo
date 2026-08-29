"""Weather tool — wraps OpenWeatherMap (current) + Open-Meteo (current + hourly).

get_weather(location) → {
    temperature, uv_index, source,
    hourly: [ {time, temp, uv_index}, ... ]   ← real data, not synthetic
}

Geocoding for Open-Meteo (which only accepts lat/lon) is handled by the
Open-Meteo geocoding endpoint so no extra API key is needed.
"""
from __future__ import annotations

import requests

from fastmcp import FastMCP
from services.config import Config

mcp = FastMCP("weather-server")

# ── helpers ────────────────────────────────────────────────────────────────

def _geocode(location: str) -> tuple[float, float] | None:
    """Resolve a city name to (lat, lon) using the Open-Meteo geocoding API."""
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": location, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            return results[0]["latitude"], results[0]["longitude"]
    except Exception:
        pass
    return None


def _fetch_open_meteo(lat: float, lon: float) -> dict:
    """Fetch current conditions AND hourly forecast from Open-Meteo."""
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude":  lat,
            "longitude": lon,
            "current":   "temperature_2m,uv_index",
            "hourly":    "temperature_2m,uv_index",
            "forecast_days": 1,
            "timezone":  "auto",
        },
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _build_hourly(meteo_data: dict) -> list[dict]:
    """Extract today's hourly slots (07:00 → 19:00) from Open-Meteo response."""
    hourly  = meteo_data.get("hourly", {})
    times   = hourly.get("time",            [])
    temps   = hourly.get("temperature_2m",  [])
    uvs     = hourly.get("uv_index",        [])

    slots = []
    for t, temp, uv in zip(times, temps, uvs):
        # t format: "2026-08-09T07:00"
        hour_str = t[11:16] if len(t) >= 16 else t
        hour = int(hour_str[:2]) if hour_str[:2].isdigit() else -1
        if 6 <= hour <= 20:
            slots.append({
                "time":     hour_str,
                "temp":     round(float(temp), 1) if temp is not None else None,
                "uv_index": round(float(uv),   1) if uv   is not None else None,
            })
    return slots


# ── registered tool ────────────────────────────────────────────────────────

@mcp.tool(name="get_weather", description="Fetch weather and UV information for a location")
def get_weather(location: str) -> dict:
    # ── path 1: OpenWeatherMap for current conditions ──────────────────────
    api_key = Config.OPENWEATHER_API_KEY
    owm_temp = None
    owm_uv   = None
    if api_key:
        try:
            r = requests.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={"q": location, "appid": api_key, "units": "metric"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            owm_temp = data.get("main", {}).get("temp")
            owm_uv   = data.get("uv")          # only present in older endpoint; often None
        except Exception:
            pass

    # ── path 2: Open-Meteo for current + full hourly (always attempted) ────
    hourly: list[dict] = []
    meteo_temp = None
    meteo_uv   = None
    meteo_source = "open-meteo"

    # Try geocoding the location string first; fall back to Chicago coords
    coords = _geocode(location) if location else None
    lat, lon = coords if coords else (41.8781, -87.6298)

    try:
        meteo_data = _fetch_open_meteo(lat, lon)
        current    = meteo_data.get("current", {})
        meteo_temp = current.get("temperature_2m")
        meteo_uv   = current.get("uv_index")
        hourly     = _build_hourly(meteo_data)
    except Exception:
        meteo_source = "fallback"

    # Prefer OWM temp if available (more accurate for exact city), fall to meteo
    final_temp = owm_temp if owm_temp is not None else meteo_temp
    final_uv   = owm_uv   if owm_uv   is not None else meteo_uv
    source     = "openweather+open-meteo" if owm_temp is not None else meteo_source

    return {
        "temperature": f"{round(final_temp, 1)}°C" if final_temp is not None else "unavailable",
        "uv_index":    round(float(final_uv), 1)   if final_uv   is not None else "unavailable",
        "source":      source,
        "hourly":      hourly,      # ← real hourly data
        "lat":         lat,
        "lon":         lon,
    }


class WeatherTool:
    def get_weather(self, location: str) -> dict:
        return get_weather(location)


if __name__ == "__main__":
    mcp.run()
