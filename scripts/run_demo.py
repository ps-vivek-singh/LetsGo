"""Quick demo — runs a single structured briefing query and prints results.

Run with:  python scripts/run_demo.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from agents.orchestrator import OrchestratorAgent


if __name__ == "__main__":
    orchestrator = OrchestratorAgent()
    query = (
        "I'm leaving from Chicago. Give me today's weather and UV, "
        "quick news, commute advice, and a 10-minute breakfast idea with eggs."
    )
    print(orchestrator.run(query))
