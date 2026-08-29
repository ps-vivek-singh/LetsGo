"""Evaluator for Agentic ReAct Trajectory and Tool Calling."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from agents.orchestrator import OrchestratorAgent

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "trajectory_golden.json"


def evaluate_agent_trajectories(dataset_path: Path | None = None) -> Dict[str, Any]:
    """Run ReAct agentic trajectory benchmark."""
    path = dataset_path or DATASET_PATH
    with open(path, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    orchestrator = OrchestratorAgent()
    loop = orchestrator.agentic_loop

    total = len(dataset)
    passed_cases = 0
    total_tools_expected = 0
    correct_tools_called = 0
    step_efficiency_passes = 0
    details: List[Dict[str, Any]] = []

    for item in dataset:
        qid = item["id"]
        query = item["query"]
        expected_tools = item["expected_tools"]
        max_steps = item.get("max_steps", 6)
        required_args_spec = item.get("required_args", {})

        result = loop.run(query, session_id=f"eval-{qid}")
        actual_tool_actions = [step.action for step in result.trace if step.action not in ("reflect", "synthesize_response", "skip", "finish_complete", "finish_incomplete")]

        # Check tool invocation accuracy
        case_tools_ok = True
        for exp_tool in expected_tools:
            total_tools_expected += 1
            if exp_tool in actual_tool_actions:
                correct_tools_called += 1
            else:
                case_tools_ok = False

        # Check step efficiency
        step_count_ok = len(result.trace) <= max_steps
        if step_count_ok:
            step_efficiency_passes += 1

        # Check args
        args_ok = True
        for step in result.trace:
            if step.action in required_args_spec:
                req_keys = required_args_spec[step.action]
                for k in req_keys:
                    if k not in step.action_args or step.action_args[k] is None:
                        args_ok = False

        case_passed = case_tools_ok and step_count_ok and args_ok
        if case_passed:
            passed_cases += 1

        details.append({
            "id": qid,
            "query": query,
            "expected_tools": expected_tools,
            "actual_tools": actual_tool_actions,
            "steps_taken": len(result.trace),
            "max_steps": max_steps,
            "tools_ok": case_tools_ok,
            "steps_ok": step_count_ok,
            "passed": case_passed,
        })

    tool_accuracy = round(correct_tools_called / total_tools_expected, 4) if total_tools_expected > 0 else 1.0
    case_accuracy = round(passed_cases / total, 4) if total > 0 else 1.0
    step_efficiency_rate = round(step_efficiency_passes / total, 4) if total > 0 else 1.0

    return {
        "category": "agent_trajectory",
        "total_test_cases": total,
        "overall_accuracy": case_accuracy,
        "tool_selection_accuracy": tool_accuracy,
        "step_efficiency_rate": step_efficiency_rate,
        "passed": case_accuracy >= 0.90,
        "details": details,
    }


if __name__ == "__main__":
    res = evaluate_agent_trajectories()
    print(json.dumps(res, indent=2))
