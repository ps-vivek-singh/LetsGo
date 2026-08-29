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

from nlp.query_parser import QueryParser
from agents.router import Router
from agents.reflection import ReflectionEngine

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
EDGE_CASES_PATH = DATASETS_DIR / "adversarial_edge_cases.json"
EXTREME_REFL_PATH = DATASETS_DIR / "extreme_reflection_matrix.json"


def evaluate_adversarial_and_edge_cases(
    edge_cases_path: Path | None = None,
    extreme_refl_path: Path | None = None,
) -> Dict[str, Any]:
    """Benchmark complex colloquial queries and extreme compound reflection conflicts."""
    p_edge = edge_cases_path or EDGE_CASES_PATH
    p_refl = extreme_refl_path or EXTREME_REFL_PATH

    with open(p_edge, "r", encoding="utf-8") as f:
        edge_cases: List[Dict[str, Any]] = json.load(f)

    with open(p_refl, "r", encoding="utf-8") as f:
        extreme_refl: List[Dict[str, Any]] = json.load(f)

    parser = QueryParser()
    router = Router()
    refl_engine = ReflectionEngine()

    # 1. Benchmark Edge-Case NLP & Slot Extraction
    edge_passed = 0
    edge_total = len(edge_cases)
    edge_details: List[Dict[str, Any]] = []

    for item in edge_cases:
        qid = item["id"]
        query = item["query"]
        expected_intents = set(item["expected_intents"])
        expected_slots = item.get("expected_slots", {})

        parsed = parser.parse(query)
        routed = set(router.route(parsed.get("sections", [])))

        intent_ok = (expected_intents == routed)
        slots_ok = True

        for k, exp_val in expected_slots.items():
            actual = parsed.get(k)
            if isinstance(exp_val, list):
                actual_list = actual if isinstance(actual, list) else []
                if not all(e in actual_list for e in exp_val):
                    slots_ok = False
            elif isinstance(exp_val, str):
                if not actual or exp_val.lower() not in str(actual).lower():
                    slots_ok = False
            else:
                if actual != exp_val:
                    slots_ok = False

        case_passed = intent_ok and slots_ok
        if case_passed:
            edge_passed += 1

        edge_details.append({
            "id": qid,
            "category": item.get("category", ""),
            "difficulty": item.get("difficulty", "medium"),
            "query": query,
            "expected_intents": list(expected_intents),
            "predicted_intents": list(routed),
            "intent_match": intent_ok,
            "slots_match": slots_ok,
            "passed": case_passed,
        })

    # 2. Benchmark Extreme Compound Reflection Conflicts
    refl_passed = 0
    refl_total = len(extreme_refl)
    refl_details: List[Dict[str, Any]] = []

    for item in extreme_refl:
        qid = item["id"]
        sections = item["sections"]
        intent = item.get("intent", {})
        exp_overrides = item.get("expected_overrides_count", 0)
        exp_mode = item.get("expected_mode_override")
        exp_alerts = item.get("expected_alert_substrings", [])
        exp_note = item.get("expected_note_substring")

        res = refl_engine.reflect(sections, intent)
        case_ok = True

        if len(res.changes_made) != exp_overrides:
            case_ok = False

        if exp_mode:
            commute_mode = sections.get("commute", {}).get("data", {}).get("recommended_mode")
            if commute_mode != exp_mode:
                case_ok = False

        if exp_alerts:
            alerts = sections.get("commute", {}).get("data", {}).get("alerts", [])
            for a_sub in exp_alerts:
                if not any(a_sub.lower() in a.lower() for a in alerts):
                    case_ok = False

        if exp_note:
            note = sections.get("breakfast", {}).get("data", {}).get("reflection_note", "")
            if exp_note.lower() not in note.lower():
                case_ok = False

        if case_ok:
            refl_passed += 1

        refl_details.append({
            "id": qid,
            "description": item.get("description", ""),
            "changes_made": res.changes_made,
            "passed": case_ok,
        })

    edge_acc = round(edge_passed / edge_total, 4) if edge_total else 1.0
    refl_acc = round(refl_passed / refl_total, 4) if refl_total else 1.0
    overall_acc = round((edge_passed + refl_passed) / (edge_total + refl_total), 4)

    return {
        "category": "adversarial_and_edge_cases",
        "total_test_cases": edge_total + refl_total,
        "edge_nlp_accuracy": edge_acc,
        "extreme_reflection_accuracy": refl_acc,
        "overall_accuracy": overall_acc,
        "passed": overall_acc >= 0.85,
        "edge_cases": edge_details,
        "extreme_reflection": refl_details,
    }


if __name__ == "__main__":
    res = evaluate_adversarial_and_edge_cases()
    print(json.dumps(res, indent=2))
