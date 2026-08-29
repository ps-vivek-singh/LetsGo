"""Central CLI Runner and Scorecard for Commute Commander Evaluation Suite.

Usage:
    python -m evals.runner
    python -m evals.runner --category intent
    python -m evals.runner --category trajectory
    python -m evals.runner --category reflection
    python -m evals.runner --category judge
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

# Ensure src/ and root are in python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from evals.evaluators.eval_intent import evaluate_intent_and_routing
from evals.evaluators.eval_trajectory import evaluate_agent_trajectories
from evals.evaluators.eval_reflection import evaluate_reflection_matrix
from evals.evaluators.eval_llm_judge import evaluate_synthesis_quality
from evals.evaluators.eval_adversarial import evaluate_adversarial_and_edge_cases
from evals.evaluators.eval_negative import evaluate_negative_constraints
from evals.evaluators.eval_multitool import evaluate_multitool_orchestration


# ── ANSI Terminal Colors ──────────────────────────────────────────────────
class _Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


def _badge(passed: bool) -> str:
    if passed:
        return f"{_Colors.GREEN}{_Colors.BOLD}[ PASSED ]{_Colors.RESET}"
    return f"{_Colors.RED}{_Colors.BOLD}[ FAILED ]{_Colors.RESET}"


def run_evals(category: str = "all", save_report: bool = True) -> int:
    """Run specified evaluations and display summary scorecard."""
    border = "=" * 72
    print("\n" + f"{_Colors.CYAN}{_Colors.BOLD}" + border + f"{_Colors.RESET}")
    print(f" {_Colors.BOLD}[*] COMMUTE COMMANDER -- AGENT EVALUATION BENCHMARK SUITE{_Colors.RESET}")
    print(f"{_Colors.CYAN}{_Colors.BOLD}" + border + f"{_Colors.RESET}")
    print(f" * Mode: {_Colors.YELLOW}{category.upper()}{_Colors.RESET} | Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{_Colors.CYAN}{_Colors.BOLD}" + border + f"{_Colors.RESET}\n")

    results: Dict[str, Any] = {}
    all_passed = True

    t0_suite = time.perf_counter()

    # 1. Intent & Routing
    if category in ("all", "intent"):
        print(f" {_Colors.DIM}Running Layer 1: NLP Intent & Slot Routing Eval...{_Colors.RESET}", end="\r", flush=True)
        res_intent = evaluate_intent_and_routing()
        results["intent_routing"] = res_intent
        if not res_intent["passed"]:
            all_passed = False

    # 2. Agent Trajectory
    if category in ("all", "trajectory"):
        print(f" {_Colors.DIM}Running Layer 2: ReAct Agentic Trajectory Eval...{_Colors.RESET}", end="\r", flush=True)
        res_traj = evaluate_agent_trajectories()
        results["agent_trajectory"] = res_traj
        if not res_traj["passed"]:
            all_passed = False

    # 3. Reflection Matrix
    if category in ("all", "reflection"):
        print(f" {_Colors.DIM}Running Layer 3: Cross-Domain Reflection Matrix Eval...{_Colors.RESET}", end="\r", flush=True)
        res_refl = evaluate_reflection_matrix()
        results["reflection_matrix"] = res_refl
        if not res_refl["passed"]:
            all_passed = False

    # 4. LLM / Heuristic Judge
    if category in ("all", "judge"):
        print(f" {_Colors.DIM}Running Layer 4: Output Synthesis & Quality Judge Eval...{_Colors.RESET}", end="\r", flush=True)
        res_judge = evaluate_synthesis_quality()
        results["synthesis_judge"] = res_judge
        if not res_judge["passed"]:
            all_passed = False

    # 5. Adversarial & Out-of-the-Box Edge Cases
    if category in ("all", "adversarial"):
        print(f" {_Colors.DIM}Running Layer 5: Adversarial & Edge-Case Benchmark Eval...{_Colors.RESET}", end="\r", flush=True)
        res_adv = evaluate_adversarial_and_edge_cases()
        results["adversarial_and_edge_cases"] = res_adv
        if not res_adv["passed"]:
            all_passed = False

    # 6. Negative Constraints & Excluded Tools
    if category in ("all", "negative"):
        print(f" {_Colors.DIM}Running Layer 6: Negative Constraints & Excluded Tools Eval...{_Colors.RESET}", end="\r", flush=True)
        res_neg = evaluate_negative_constraints()
        results["negative_constraints"] = res_neg
        if not res_neg["passed"]:
            all_passed = False

    # 7. Complex Multi-Tool Orchestration
    if category in ("all", "multitool"):
        print(f" {_Colors.DIM}Running Layer 7: Complex Multi-Tool Orchestration Eval...{_Colors.RESET}", end="\r", flush=True)
        res_multi = evaluate_multitool_orchestration()
        results["multitool_orchestration"] = res_multi
        if not res_multi["passed"]:
            all_passed = False

    total_duration_s = round(time.perf_counter() - t0_suite, 2)

    # ── Render Terminal Scorecard ──────────────────────────────────────────
    print("\n" + "─" * 72)
    print(f" {'EVALUATION CATEGORY':<28} | {'TESTS':<6} | {'SCORE / METRIC':<18} | {'STATUS':<10}")
    print("─" * 72)

    if "intent_routing" in results:
        r = results["intent_routing"]
        score_str = f"Acc: {r['exact_match_accuracy']*100:.1f}% (F1:{r['f1_score']:.2f})"
        print(f" {'1. Intent & Routing':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    if "agent_trajectory" in results:
        r = results["agent_trajectory"]
        score_str = f"Tool: {r['tool_selection_accuracy']*100:.1f}% (Eff:{r['step_efficiency_rate']*100:.0f}%)"
        print(f" {'2. Agent Trajectory':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    if "reflection_matrix" in results:
        r = results["reflection_matrix"]
        score_str = f"Pass: {r['accuracy']*100:.1f}% ({r['passed_cases']}/{r['total_test_cases']})"
        print(f" {'3. Reflection Rules':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    if "synthesis_judge" in results:
        r = results["synthesis_judge"]
        score_str = f"Faithful: {r['avg_faithfulness']:.1f}/5.0"
        print(f" {'4. Output Quality Judge':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    if "adversarial_and_edge_cases" in results:
        r = results["adversarial_and_edge_cases"]
        score_str = f"Acc: {r['overall_accuracy']*100:.1f}% (NLP:{r['edge_nlp_accuracy']*100:.0f}%)"
        print(f" {'5. Adversarial & OOD':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    if "negative_constraints" in results:
        r = results["negative_constraints"]
        score_str = f"Pass: {r['accuracy']*100:.1f}% ({r['passed_cases']}/{r['total_test_cases']})"
        print(f" {'6. Negative Constraints':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    if "multitool_orchestration" in results:
        r = results["multitool_orchestration"]
        score_str = f"Pass: {r['accuracy']*100:.1f}% ({r['passed_cases']}/{r['total_test_cases']})"
        print(f" {'7. Multi-Tool Orch':<28} | {r['total_test_cases']:<6} | {score_str:<18} | {_badge(r['passed'])}")

    print("─" * 72)

    status_str = f"{_Colors.GREEN}{_Colors.BOLD}ALL EVALS PASSED{_Colors.RESET}" if all_passed else f"{_Colors.RED}{_Colors.BOLD}SOME EVALS FAILED{_Colors.RESET}"
    print(f" Result: {status_str} (Completed in {total_duration_s}s)\n")

    # ── Save Report JSON ───────────────────────────────────────────────────
    if save_report:
        results_dir = PROJECT_ROOT / "evals" / "results"
        results_dir.mkdir(parents=True, exist_ok=True)
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = results_dir / f"report_{timestamp_str}.json"

        report_payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "all_passed": all_passed,
            "duration_seconds": total_duration_s,
            "results": results,
        }

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_payload, f, indent=2, default=str)

        print(f" {_Colors.DIM}Benchmark report saved to: {report_path.relative_to(PROJECT_ROOT)}{_Colors.RESET}\n")

    return 0 if all_passed else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Commute Commander Evaluation Runner")
    parser.add_argument(
        "--category",
        choices=["all", "intent", "trajectory", "reflection", "judge", "adversarial", "negative", "multitool"],
        default="all",
        help="Evaluation category to benchmark (default: all)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Do not save JSON report file to disk",
    )
    args = parser.parse_args()
    exit_code = run_evals(category=args.category, save_report=not args.no_save)
    sys.exit(exit_code)


