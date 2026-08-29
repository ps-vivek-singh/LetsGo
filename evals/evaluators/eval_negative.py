"""Evaluator for Negative Constraints and Excluded Intent/Tool Benchmarks."""
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

DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
NEGATIVE_GOLDEN_PATH = DATASETS_DIR / "negative_golden.json"


def evaluate_negative_constraints(dataset_path: Path | None = None) -> Dict[str, Any]:
    """Benchmark negative constraints, excluded intents, and out-of-scope rejections."""
    p = dataset_path or NEGATIVE_GOLDEN_PATH
    with open(p, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    parser = QueryParser()
    router = Router()

    passed_cases = 0
    total_cases = len(dataset)
    details: List[Dict[str, Any]] = []

    for item in dataset:
        qid = item["id"]
        query = item["query"]
        expected_intents = set(item["expected_intents"])
        excluded_intents = set(item.get("excluded_intents", []))

        parsed = parser.parse(query)
        routed = set(router.route(parsed.get("sections", [])))

        # 1. Exact match of allowed intents
        intents_ok = (routed == expected_intents)

        # 2. Strict negative check: none of the excluded intents should be in routed
        negative_ok = len(routed.intersection(excluded_intents)) == 0

        case_passed = intents_ok and negative_ok
        if case_passed:
            passed_cases += 1

        details.append({
            "id": qid,
            "category": item.get("category", ""),
            "query": query,
            "expected_intents": list(expected_intents),
            "excluded_intents": list(excluded_intents),
            "routed_intents": list(routed),
            "intents_match": intents_ok,
            "exclusion_enforced": negative_ok,
            "passed": case_passed,
        })

    accuracy = round(passed_cases / total_cases, 4) if total_cases else 1.0

    return {
        "category": "negative_constraints",
        "total_test_cases": total_cases,
        "passed_cases": passed_cases,
        "accuracy": accuracy,
        "passed": accuracy >= 0.90,
        "details": details,
    }


if __name__ == "__main__":
    res = evaluate_negative_constraints()
    print(json.dumps(res, indent=2))
