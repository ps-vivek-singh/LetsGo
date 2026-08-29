"""Commute tool — real routing via TomTom Routing API with India support.

get_route(location, destination, mode) -> dict:
    {
        "recommended_mode": str,
        "eta_minutes":      int,
        "distance_km":      float,
        "alerts":           list[str],
        "alternates": [
            { "mode": str, "eta_minutes": int, "distance_km": float,
              "polyline": [[lat,lon], ...] },
            ...
        ],
        "polyline":  [[lat, lon], ...],   # decoded from TomTom response
        "origin":    { "lat": float, "lon": float, "label": str },
        "dest":      { "lat": float, "lon": float, "label": str },
        "source":    str,
    }

Fallback path (no key / API error) returns a plausible advisory dict so
the rest of the system keeps working.
"""
from __future__ import annotations

import requests

from fastmcp import FastMCP
from services.config import Config

mcp = FastMCP("commute-server")

# TomTom travelMode values that map to our UI modes
_TT_MODES = {
    "drive":   "car",
    "transit": "car",   # TomTom free tier has no transit; use car as proxy
    "bike":    "bicycle",
    "walk":    "pedestrian",
}


# ── Geocoding ──────────────────────────────────────────────────────────────

def _geocode_tomtom(query: str, api_key: str) -> tuple[float, float, str] | None:
    """Resolve a free-text address to (lat, lon, formatted_label) via TomTom Search."""
    try:
        r = requests.get(
            "https://api.tomtom.com/search/2/geocode/{q}.json".format(
                q=requests.utils.quote(query)
            ),
            params={"key": api_key, "limit": 1},
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            pos   = results[0]["position"]
            label = results[0].get("address", {}).get("freeformAddress", query)
            return pos["lat"], pos["lon"], label
    except Exception:
        pass
    return None


def _geocode_nominatim(query: str) -> tuple[float, float, str] | None:
    """OpenStreetMap Nominatim geocoding — free, no key, great India coverage."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "json",
                "limit": 1,
                "addressdetails": 1,
            },
            headers={"User-Agent": "CommuteCommander/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            res = results[0]
            lat = float(res["lat"])
            lon = float(res["lon"])
            label = res.get("display_name", query)
            # Shorten the display_name to city + country
            parts = label.split(",")
            short = ", ".join(p.strip() for p in parts[:3])
            return lat, lon, short
    except Exception:
        pass
    return None


def _geocode_open_meteo(query: str) -> tuple[float, float, str] | None:
    """No-key geocoding fallback using Open-Meteo geocoding API."""
    try:
        r = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": query, "count": 1, "language": "en", "format": "json"},
            timeout=8,
        )
        r.raise_for_status()
        results = r.json().get("results", [])
        if results:
            res = results[0]
            label = f"{res.get('name', query)}, {res.get('country', '')}"
            return res["latitude"], res["longitude"], label.strip(", ")
    except Exception:
        pass
    return None


def _geocode(query: str, api_key: str) -> tuple[float, float, str] | None:
    """Try TomTom → Nominatim → Open-Meteo geocoding cascade."""
    if api_key:
        result = _geocode_tomtom(query, api_key)
        if result:
            return result
    # Try Nominatim (great for Indian cities)
    result = _geocode_nominatim(query)
    if result:
        return result
    return _geocode_open_meteo(query)


# ── Polyline decoding ──────────────────────────────────────────────────────

def _decode_tomtom_polyline(points_list: list[dict]) -> list[list[float]]:
    """Convert TomTom's points array [{"latitude":..,"longitude":..}] to [[lat,lon],...]."""
    return [[p["latitude"], p["longitude"]] for p in points_list]


# ── Routing call ───────────────────────────────────────────────────────────

def _call_tomtom_route(
    origin_lat: float, origin_lon: float,
    dest_lat: float,   dest_lon: float,
    tt_mode: str,      api_key: str,
) -> dict | None:
    """Call TomTom Calculate Route and return the first route summary + points."""
    try:
        url = (
            f"https://api.tomtom.com/routing/1/calculateRoute/"
            f"{origin_lat},{origin_lon}:{dest_lat},{dest_lon}/json"
        )
        r = requests.get(
            url,
            params={
                "key":          api_key,
                "travelMode":   tt_mode,
                "traffic":      "true",
                "routeType":    "fastest",
                "maxAlternatives": 0,
            },
            timeout=12,
        )
        r.raise_for_status()
        data   = r.json()
        routes = data.get("routes", [])
        if not routes:
            return None

        route   = routes[0]
        summary = route.get("summary", {})
        legs    = route.get("legs", [])
        points: list[dict] = []
        for leg in legs:
            points.extend(leg.get("points", []))

        return {
            "eta_minutes": round(summary.get("travelTimeInSeconds", 0) / 60),
            "distance_km": round(summary.get("lengthInMeters", 0) / 1000, 1),
            "polyline":    _decode_tomtom_polyline(points),
            "traffic_delay_s": summary.get("trafficDelayInSeconds", 0),
        }
    except Exception:
        return None


# ── ORS (OpenRouteService) fallback for non-car modes ─────────────────────

def _call_ors_route(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    profile: str,  # "driving-car", "cycling-regular", "foot-walking"
) -> dict | None:
    """Free OpenRouteService routing — no key needed for basic use."""
    try:
        r = requests.get(
            f"https://api.openrouteservice.org/v2/directions/{profile}",
            params={
                "api_key": "5b3ce3597851110001cf62488082efec9de747d3a8ebe748f3d5a069",  # public demo key
                "start": f"{origin_lon},{origin_lat}",
                "end": f"{dest_lon},{dest_lat}",
            },
            timeout=12,
        )
        if not r.ok:
            return None
        data = r.json()
        features = data.get("features", [])
        if not features:
            return None
        props = features[0].get("properties", {})
        summary = props.get("summary", {})
        coords = features[0].get("geometry", {}).get("coordinates", [])
        polyline = [[c[1], c[0]] for c in coords]  # ORS returns [lon,lat]
        return {
            "eta_minutes": round(summary.get("duration", 0) / 60),
            "distance_km": round(summary.get("distance", 0) / 1000, 1),
            "polyline": polyline,
            "traffic_delay_s": 0,
        }
    except Exception:
        return None


# ── Registered tool ────────────────────────────────────────────────────────

@mcp.tool(
    name="get_commute_route",
    description="Get real commute routing data between two locations",
)
def get_commute_route(location: str, destination: str = "", mode: str = "drive") -> dict:
    """Return routing data for all supported modes.

    `location`    -- origin (e.g. "Mumbai, India" or "Chicago, IL")
    `destination` -- explicit destination; defaults to city centre of location
    `mode`        -- primary mode: "drive" | "transit" | "bike" | "walk"
    """
    api_key = Config.TOMTOM_API_KEY
    # Normalise mode
    mode = mode.lower().strip() if mode else "drive"
    if mode not in ("drive", "transit", "bike", "walk"):
        mode = "drive"

    # Geocode origin
    origin = _geocode(location, api_key) if location else None
    if not origin:
        origin = (20.5937, 78.9629, "India")
    orig_lat, orig_lon, orig_label = origin

    # Destination: use provided string or pick a nearby point
    dest_query = destination if destination else f"{location} city centre"
    dest = _geocode(dest_query, api_key)
    if not dest:
        dest = (orig_lat + 0.07, orig_lon + 0.06, f"Downtown {location}")
    dest_lat, dest_lon, dest_label = dest

    # -- TomTom routing --
    if api_key:
        drive_data = _call_tomtom_route(orig_lat, orig_lon, dest_lat, dest_lon, "car",        api_key)
        bike_data  = _call_tomtom_route(orig_lat, orig_lon, dest_lat, dest_lon, "bicycle",    api_key)
        walk_data  = _call_tomtom_route(orig_lat, orig_lon, dest_lat, dest_lon, "pedestrian", api_key)

        if drive_data:
            delay_s = drive_data.get("traffic_delay_s", 0)
            alerts  = [f"Traffic delay of ~{round(delay_s/60)} min on recommended route."] \
                      if delay_s > 300 else []

            all_modes = {
                "drive":   drive_data,
                "transit": {
                    "eta_minutes": drive_data["eta_minutes"] + 12,
                    "distance_km": drive_data["distance_km"],
                    "polyline":    drive_data["polyline"],
                    "traffic_delay_s": 0,
                },
            }
            if bike_data:
                all_modes["bike"] = bike_data
            if walk_data:
                all_modes["walk"] = walk_data

            primary_mode = mode if mode in all_modes else "drive"
            primary_data = all_modes[primary_mode]

            alternates = [
                {
                    "mode":        m,
                    "eta_minutes": d["eta_minutes"],
                    "distance_km": d["distance_km"],
                    "polyline":    d["polyline"],
                }
                for m, d in all_modes.items() if m != primary_mode
            ]

            return {
                "recommended_mode": primary_mode,
                "eta_minutes":      primary_data["eta_minutes"],
                "distance_km":      primary_data["distance_km"],
                "alerts":           alerts,
                "alternates":       alternates,
                "polyline":         primary_data["polyline"],
                "origin":           {"lat": orig_lat, "lon": orig_lon, "label": orig_label},
                "dest":             {"lat": dest_lat, "lon": dest_lon, "label": dest_label},
                "source":           "tomtom",
            }

    # -- ORS fallback (no TomTom key) --
    _ORS_PROFILES = {"bike": "cycling-regular", "walk": "foot-walking", "drive": "driving-car"}
    ors_profile = _ORS_PROFILES.get(mode, "driving-car")
    ors_data = _call_ors_route(orig_lat, orig_lon, dest_lat, dest_lon, ors_profile)
    if ors_data:
        drive_ors = _call_ors_route(orig_lat, orig_lon, dest_lat, dest_lon, "driving-car") or {}
        eta  = ors_data["eta_minutes"]
        dist = ors_data["distance_km"]
        alts = []
        if mode != "drive" and drive_ors:
            alts.append({"mode": "drive",   "eta_minutes": drive_ors.get("eta_minutes", eta), "distance_km": drive_ors.get("distance_km", dist), "polyline": drive_ors.get("polyline", [])})
        if mode != "transit":
            alts.append({"mode": "transit", "eta_minutes": drive_ors.get("eta_minutes", eta + 12) + 12, "distance_km": dist, "polyline": []})
        return {
            "recommended_mode": mode,
            "eta_minutes":      eta,
            "distance_km":      dist,
            "alerts":           [f"Leave 15-20 min early for {dest_query} traffic."],
            "alternates":       alts,
            "polyline":         ors_data["polyline"],
            "origin":           {"lat": orig_lat, "lon": orig_lon, "label": orig_label},
            "dest":             {"lat": dest_lat, "lon": dest_lon, "label": dest_label},
            "source":           "ors",
        }

    # -- Advisory fallback --
    eta  = 35
    dist = 15.0
    return {
        "recommended_mode": mode,
        "eta_minutes":      eta,
        "distance_km":      dist,
        "alerts":           [f"Leave 15-20 min early for {location} traffic."],
        "alternates": [
            {"mode": "transit", "eta_minutes": eta + 15, "distance_km": dist, "polyline": []},
            {"mode": "bike",    "eta_minutes": eta + 30, "distance_km": dist, "polyline": []},
        ],
        "polyline": [],
        "origin":   {"lat": orig_lat, "lon": orig_lon, "label": orig_label},
        "dest":     {"lat": dest_lat, "lon": dest_lon, "label": dest_label},
        "source":   "advisory",
    }


# Keep backward-compat name for any existing callers (CLI run())
@mcp.tool(
    name="get_commute_advice",
    description="Plain-text commute advice (legacy CLI path)",
)
def get_commute_advice(location: str) -> str:
    data = get_commute_route(location)
    eta  = data["eta_minutes"]
    mode = data["recommended_mode"]
    if data["alerts"]:
        return data["alerts"][0]
    return f"Recommended: {mode} — approx. {eta} min to {data['dest']['label']}."


class CommuteTool:
    def get_commute_route(self, location: str, destination: str = "", mode: str = "drive") -> dict:
        return get_commute_route(location, destination, mode)

    # legacy shim
    def get_commute_advice(self, location: str) -> str:
        return get_commute_advice(location)


if __name__ == "__main__":
    mcp.run()
