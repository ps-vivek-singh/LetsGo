import math
import re
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


# ── Distance & Math Utilities ──────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate approximate road distance in km using Haversine formula with a 1.3 winding factor."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(R * c * 1.3, 1)


def _clean_location(loc_str: str) -> str:
    """Clean conversational noise words from location strings."""
    if not loc_str:
        return ""
    cleaned = re.sub(r"(?i)\b(commute\s+to|commute\s+from|from|to|route\s+to|directions\s+to)\b", " ", loc_str)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or loc_str


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
            headers={"User-Agent": "LetsGo/1.0"},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json()
        if results:
            res = results[0]
            lat = float(res["lat"])
            lon = float(res["lon"])
            label = res.get("display_name", query)
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


def _geocode(query: str, api_key: str = "") -> tuple[float, float, str] | None:
    """Try TomTom → Nominatim → Open-Meteo geocoding cascade."""
    q_clean = _clean_location(query)
    if api_key:
        result = _geocode_tomtom(q_clean, api_key)
        if result:
            return result
    result = _geocode_nominatim(q_clean)
    if result:
        return result
    return _geocode_open_meteo(q_clean)


# ── Polyline decoding ──────────────────────────────────────────────────────

def _decode_tomtom_polyline(points_list: list[dict]) -> list[list[float]]:
    """Convert TomTom's points array [{"latitude":..,"longitude":..}] to [[lat,lon],...]."""
    return [[p["latitude"], p["longitude"]] for p in points_list]


# ── Routing Engine 1: TomTom ───────────────────────────────────────────────

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
            timeout=10,
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


# ── Routing Engine 2: OSRM (Open Source Routing Machine — Free & Public) ───

def _call_osrm_route(
    origin_lat: float, origin_lon: float,
    dest_lat: float, dest_lon: float,
    mode: str = "drive",
) -> dict | None:
    """Call OSRM public API to get turn-by-turn routing, distance, duration, and polylines."""
    try:
        osrm_profile = "driving"
        if mode == "bike":
            osrm_profile = "bike"
        elif mode == "walk":
            osrm_profile = "foot"

        url = (
            f"https://router.project-osrm.org/route/v1/{osrm_profile}/"
            f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
            f"?overview=full&geometries=geojson"
        )
        r = requests.get(url, headers={"User-Agent": "LetsGo/1.0"}, timeout=8)
        if not r.ok:
            # Fallback to driving profile if mode-specific profile is unavailable
            url = (
                f"https://router.project-osrm.org/route/v1/driving/"
                f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
                f"?overview=full&geometries=geojson"
            )
            r = requests.get(url, headers={"User-Agent": "LetsGo/1.0"}, timeout=8)
            if not r.ok:
                return None

        data = r.json()
        routes = data.get("routes", [])
        if not routes:
            return None

        route = routes[0]
        dur_s = route.get("duration", 0)
        dist_m = route.get("distance", 0)
        coords = route.get("geometry", {}).get("coordinates", [])

        polyline = [[c[1], c[0]] for c in coords]  # Convert [lon, lat] to [lat, lon]

        return {
            "eta_minutes": max(1, round(dur_s / 60.0)),
            "distance_km": round(dist_m / 1000.0, 1),
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

    # Extract embedded "Origin to Destination" strings if destination is empty
    orig_str = location
    dest_str = destination
    if not dest_str and " to " in orig_str.lower():
        parts = re.split(r"\s+to\s+", orig_str, flags=re.IGNORECASE)
        if len(parts) >= 2:
            orig_str, dest_str = parts[0].strip(), parts[1].strip()

    # Geocode origin
    origin = _geocode(orig_str, api_key) if orig_str else None
    if not origin:
        origin = (20.5937, 78.9629, orig_str or "Origin")
    orig_lat, orig_lon, orig_label = origin

    # Destination: use provided string or pick a nearby point
    dest_query = dest_str if dest_str else f"{orig_str} city centre"
    dest = _geocode(dest_query, api_key)
    if not dest:
        dest = (orig_lat + 0.05, orig_lon + 0.05, dest_query)
    dest_lat, dest_lon, dest_label = dest

    # ── Path 1: TomTom API ────────────────────────────────────────────────
    if api_key:
        drive_data = _call_tomtom_route(orig_lat, orig_lon, dest_lat, dest_lon, "car", api_key)
        if drive_data:
            bike_data = _call_tomtom_route(orig_lat, orig_lon, dest_lat, dest_lon, "bicycle", api_key)
            walk_data = _call_tomtom_route(orig_lat, orig_lon, dest_lat, dest_lon, "pedestrian", api_key)
            dist_km = drive_data["distance_km"]

            all_modes = {
                "drive": drive_data,
                "transit": {
                    "eta_minutes": max(5, round((dist_km / 22.0) * 60 + 8)),
                    "distance_km": dist_km,
                    "polyline": drive_data["polyline"],
                    "traffic_delay_s": 0,
                },
                "bike": bike_data or {
                    "eta_minutes": max(3, round((dist_km / 15.0) * 60)),
                    "distance_km": dist_km,
                    "polyline": drive_data["polyline"],
                    "traffic_delay_s": 0,
                },
                "walk": walk_data or {
                    "eta_minutes": max(2, round((dist_km / 4.5) * 60)),
                    "distance_km": dist_km,
                    "polyline": drive_data["polyline"],
                    "traffic_delay_s": 0,
                },
            }

            primary_data = all_modes[mode]
            delay_s = primary_data.get("traffic_delay_s", 0)
            alerts = [f"Traffic delay of ~{round(delay_s / 60)} min on recommended route."] if delay_s > 300 else []

            alternates = [
                {
                    "mode": m,
                    "eta_minutes": d["eta_minutes"],
                    "distance_km": d["distance_km"],
                    "polyline": d["polyline"],
                }
                for m, d in all_modes.items() if m != mode
            ]

            return {
                "recommended_mode": mode,
                "eta_minutes": primary_data["eta_minutes"],
                "distance_km": primary_data["distance_km"],
                "alerts": alerts,
                "alternates": alternates,
                "polyline": primary_data["polyline"],
                "origin": {"lat": orig_lat, "lon": orig_lon, "label": orig_label},
                "dest": {"lat": dest_lat, "lon": dest_lon, "label": dest_label},
                "source": "tomtom",
            }

    # ── Path 2: OSRM Public Routing Engine (Zero Key Required) ───────────
    drive_osrm = _call_osrm_route(orig_lat, orig_lon, dest_lat, dest_lon, "drive")
    if drive_osrm:
        dist_km = drive_osrm["distance_km"]
        bike_osrm = _call_osrm_route(orig_lat, orig_lon, dest_lat, dest_lon, "bike")
        walk_osrm = _call_osrm_route(orig_lat, orig_lon, dest_lat, dest_lon, "walk")

        all_modes = {
            "drive": drive_osrm,
            "transit": {
                "eta_minutes": max(5, round((dist_km / 22.0) * 60 + 8)),
                "distance_km": dist_km,
                "polyline": drive_osrm["polyline"],
                "traffic_delay_s": 0,
            },
            "bike": {
                "eta_minutes": (
                    bike_osrm["eta_minutes"]
                    if bike_osrm and bike_osrm["eta_minutes"] > drive_osrm["eta_minutes"]
                    else max(3, round((dist_km / 15.0) * 60))
                ),
                "distance_km": dist_km,
                "polyline": (bike_osrm["polyline"] if bike_osrm else drive_osrm["polyline"]),
                "traffic_delay_s": 0,
            },
            "walk": {
                "eta_minutes": (
                    walk_osrm["eta_minutes"]
                    if walk_osrm and walk_osrm["eta_minutes"] > drive_osrm["eta_minutes"] * 2
                    else max(2, round((dist_km / 4.5) * 60))
                ),
                "distance_km": dist_km,
                "polyline": (walk_osrm["polyline"] if walk_osrm else drive_osrm["polyline"]),
                "traffic_delay_s": 0,
            },
        }

        primary_data = all_modes[mode]
        alternates = [
            {
                "mode": m,
                "eta_minutes": d["eta_minutes"],
                "distance_km": d["distance_km"],
                "polyline": d["polyline"],
            }
            for m, d in all_modes.items() if m != mode
        ]

        return {
            "recommended_mode": mode,
            "eta_minutes": primary_data["eta_minutes"],
            "distance_km": primary_data["distance_km"],
            "alerts": [],
            "alternates": alternates,
            "polyline": primary_data["polyline"],
            "origin": {"lat": orig_lat, "lon": orig_lon, "label": orig_label},
            "dest": {"lat": dest_lat, "lon": dest_lon, "label": dest_label},
            "source": "osrm",
        }

    # ── Path 3: Geocoded Haversine Road Engine ─────────────────────────────
    dist_km = _haversine_km(orig_lat, orig_lon, dest_lat, dest_lon)
    straight_polyline = [[orig_lat, orig_lon], [dest_lat, dest_lon]]

    all_modes = {
        "drive": {
            "eta_minutes": max(4, round((dist_km / 45.0) * 60)),
            "distance_km": dist_km,
            "polyline": straight_polyline,
        },
        "transit": {
            "eta_minutes": max(8, round((dist_km / 22.0) * 60 + 8)),
            "distance_km": dist_km,
            "polyline": straight_polyline,
        },
        "bike": {
            "eta_minutes": max(5, round((dist_km / 15.0) * 60)),
            "distance_km": dist_km,
            "polyline": straight_polyline,
        },
        "walk": {
            "eta_minutes": max(3, round((dist_km / 4.5) * 60)),
            "distance_km": dist_km,
            "polyline": straight_polyline,
        },
    }

    primary_data = all_modes[mode]
    alternates = [
        {
            "mode": m,
            "eta_minutes": d["eta_minutes"],
            "distance_km": d["distance_km"],
            "polyline": d["polyline"],
        }
        for m, d in all_modes.items() if m != mode
    ]

    return {
        "recommended_mode": mode,
        "eta_minutes": primary_data["eta_minutes"],
        "distance_km": primary_data["distance_km"],
        "alerts": [f"Estimated distance ~{dist_km} km."],
        "alternates": alternates,
        "polyline": straight_polyline,
        "origin": {"lat": orig_lat, "lon": orig_lon, "label": orig_label},
        "dest": {"lat": dest_lat, "lon": dest_lon, "label": dest_label},
        "source": "haversine",
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
