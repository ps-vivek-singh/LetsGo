"""Settings persistence — stores user preferences in settings.json.

Schema:
{
  "default_location": str,
  "units":            "metric" | "imperial",
  "default_sections": list[str],
  "news_categories":  list[str]
}
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

# Default: project_root/config (two levels above src/services/)
_DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "config"

_DEFAULTS: Dict[str, Any] = {
    "default_location": "",
    "units": "metric",
    "default_sections": ["weather", "commute", "news", "breakfast"],
    "news_categories": ["general"],
}

_ALLOWED_SECTIONS = {"weather", "commute", "news", "breakfast"}
_ALLOWED_UNITS    = {"metric", "imperial"}


class SettingsManager:
    def __init__(self, storage_dir: str | None = None) -> None:
        self._path = os.path.join(
            storage_dir or str(_DEFAULT_CONFIG_DIR), "settings.json"
        )

    def load(self) -> Dict[str, Any]:
        """Return current settings, falling back to defaults for missing keys."""
        if not os.path.exists(self._path):
            return dict(_DEFAULTS)
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                stored = json.load(fh)
            return {**_DEFAULTS, **stored}
        except Exception:
            return dict(_DEFAULTS)

    def save(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Merge validated updates into current settings and persist."""
        current = self.load()

        if "default_location" in updates:
            current["default_location"] = str(updates["default_location"])

        if "units" in updates:
            val = str(updates["units"])
            if val in _ALLOWED_UNITS:
                current["units"] = val

        if "default_sections" in updates:
            secs = [s for s in updates["default_sections"] if s in _ALLOWED_SECTIONS]
            current["default_sections"] = secs

        if "news_categories" in updates:
            current["news_categories"] = [str(c) for c in updates["news_categories"]]

        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(current, fh, indent=2)

        return current
