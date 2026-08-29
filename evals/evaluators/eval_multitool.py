"""Evaluator for Complex Multi-Tool Orchestration Trajectories."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agents.orchestrator import OrchestratorAgent

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
MULTITOOL_PATH = DATASETS_DIR / "multitool_orchestration_golden.json"


def evaluate_multitool_orchestration(dataset_path: Path | None = None) -> Dict[str, Any]:
    """Benchmark complex 3-tool and 4-tool orchestrations in ReAct AgenticLoop."""
    p = dataset_path or MULTITOOL_PATH
    with open(p, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    orchestrator = OrchestratorAgent()
    loop = orchestrator.agentic_loop

    total_cases = len(dataset)
    passed_cases = 0
    details: List[Dict[str, Any]] = []

    for item in dataset:
        qid = item["id"]
        query = item["query"]
        expected_tools = set(item["expected_tools"])
        expected_sections = set(item.get("expected_sections", []))
        min_tools_count = item.get("min_tools_count", len(expected_tools))
        max_steps = item.get("max_steps", 7)

        # Run multi-tool orchestration through AgenticLoop
        result = loop.run(query, session_id=f"eval-multi-{qid}")

        # Extract executed tools from trajectory trace
        actual_tools = [
            step.action
            for step in result.trace
            if step.action not in ("reflect", "synthesize_response", "skip", "finish_complete", "finish_incomplete")
        ]
        actual_tool_set = set(actual_tools)
        actual_sections = set(result.sections.keys())

        # 1. Check all expected tools were invoked
        tools_invoked_ok = expected_tools.issubset(actual_tool_set)
        # 2. Check total tool count satisfies minimum orchestration depth
        tool_count_ok = len(actual_tools) >= min_tools_count
        # 3. Check section data was populated
        sections_ok = expected_sections.issubset(actual_sections)
        # 4. Check step efficiency
        steps_ok = len(result.trace) <= max_steps

        case_passed = tools_invoked_ok and tool_count_ok and sections_ok and steps_ok
        if case_passed:
            passed_cases += 1

        details.append({
            "id": qid,
            "description": item.get("description", ""),
            "query": query,
            "expected_tools": list(expected_tools),
            "actual_tools": actual_tools,
            "total_steps": len(result.trace),
            "tools_invoked_ok": tools_invoked_ok,
            "tool_count_ok": tool_count_ok,
            "sections_ok": sections_ok,
            "steps_ok": steps_ok,
            "passed": case_passed,
        })

    accuracy = round(passed_cases / total_cases, 4) if total_cases else 1.0

    return {
        "category": "multitool_orchestration",
        "total_test_cases": total_cases,
        "passed_cases": passed_cases,
        "accuracy": accuracy,
        "passed": accuracy >= 0.80,
        "details": details,
    }


if __name__ == "__main__":
    res = evaluate_multitool_orchestration()
    print(json.dumps(res, indent=2))
