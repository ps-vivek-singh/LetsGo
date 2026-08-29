"""CLI entry point for Commute Commander.

Run with:  python scripts/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to path so package imports resolve
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT / "src"))

from agents.orchestrator import OrchestratorAgent
from services.session_manager import SessionManager


def main() -> None:
    print("Commute Commander")
    print("Type 'quit' to exit.\n")
    session_manager = SessionManager()
    orchestrator = OrchestratorAgent(session_manager=session_manager)
    user_id = input("Enter your name or user id: ").strip() or "guest"
    session_id = session_manager.start_session(user_id)

    print(f"Session started: {session_id}\n")

    while True:
        query = input("You: ").strip()
        if not query:
            continue
        if query.lower() in {"quit", "exit"}:
            print("Goodbye!")
            break

        briefing = orchestrator.run(query, session_id=session_id)
        print("\nMorning Briefing:\n")
        print(briefing)
        print()


if __name__ == "__main__":
    main()
