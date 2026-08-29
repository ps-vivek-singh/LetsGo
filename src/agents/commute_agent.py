"""CommuteAgent — wraps CommuteTool and shapes output for UI cards.

run()            → plain text  (CLI / legacy)
run_structured() → typed dict  (web API §3.3 + polyline for Leaflet)
"""
from __future__ import annotations

from mcp_tools.commute_tools import CommuteTool

_MODE_LABELS = {
    "drive":   "Drive",
    "transit": "Transit",
    "bike":    "Bike",
    "walk":    "Walk",
}


class CommuteAgent:
    def __init__(self) -> None:
        self.tool = CommuteTool()

    # ── CLI / legacy ───────────────────────────────────────────────────────
    def run(self, location: str) -> str:
        advice = self.tool.get_commute_advice(location)
        return f"## Commute\n- {advice}"

    # ── Structured (web API §3.3 + polyline) ──────────────────────────────
    def run_structured(self, location: str, destination: str = "", mode: str = "drive") -> dict:
        """Return typed dict matching API contract §3.3 shape.

        Extra non-contract fields accepted by the UI:
          data.polyline      [[lat,lon],...] for Leaflet route overlay
          data.origin        {lat, lon, label}
          data.dest          {lat, lon, label}
          data.distance_km   float
          data.source        "tomtom" | "advisory"
        """
        try:
            raw = self.tool.get_commute_route(location, destination, mode)
        except Exception as exc:
            return {
                "section": "commute",
                "status":  "error",
                "error":   {"code": "routing_error", "message": str(exc)},
            }

        mode      = raw.get("recommended_mode", "drive")
        eta       = raw.get("eta_minutes", 28)
        dist      = raw.get("distance_km", 0.0)
        alerts    = raw.get("alerts", [])
        polyline  = raw.get("polyline", [])
        origin    = raw.get("origin", {})
        dest      = raw.get("dest", {})
        source    = raw.get("source", "advisory")

        # Shape alternates to match the API contract
        alternates = [
            {
                "mode":        alt.get("mode", ""),
                "eta_minutes": alt.get("eta_minutes", 0),
                "distance_km": alt.get("distance_km", 0.0),
                "polyline":    alt.get("polyline", []),
            }
            for alt in raw.get("alternates", [])
        ]

        return {
            "section": "commute",
            "status":  "success",
            "data": {
                # ── API contract §3.3 fields ──
                "recommended_mode": mode,
                "eta_minutes":      eta,
                "alerts":           alerts,
                "alternates":       alternates,
                # ── Extra fields for Leaflet map + UI cards ──
                "distance_km":      dist,
                "polyline":         polyline,
                "origin":           origin,
                "dest":             dest,
                "source":           source,
                "mode_label":       _MODE_LABELS.get(mode, mode.capitalize()),
            },
        }
