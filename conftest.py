"""conftest.py — makes pytest find the src/ packages without installation.

Adds the project root to sys.path so that `from agents.X import Y` resolves
to `src/agents/X.py` when running tests from the project root.
"""
import sys
from pathlib import Path

# Insert src/ so that `from agents.X import Y` works in all tests
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
