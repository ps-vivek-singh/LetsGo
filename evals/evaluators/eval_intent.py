"""Evaluator for Intent Classification and Slot Extraction."""
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

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "routing_golden.json"


def evaluate_intent_and_routing(dataset_path: Path | None = None) -> Dict[str, Any]:
    """Run intent and slot extraction benchmark against golden dataset."""
    path = dataset_path or DATASET_PATH
    with open(path, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    parser = QueryParser()
    router = Router()

    total = len(dataset)
    exact_intent_matches = 0
    total_slots_tested = 0
    correct_slots = 0

    tp = 0
    fp = 0
    fn = 0

    results_detail: List[Dict[str, Any]] = []

    for item in dataset:
        qid = item["id"]
        query = item["query"]
        expected_intents = set(item["expected_intents"])
        expected_slots = item.get("expected_slots", {})

        parsed = parser.parse(query)
        routed = set(router.route(parsed.get("sections", [])))

        # Intent comparison
        tp += len(expected_intents.intersection(routed))
        fp += len(routed - expected_intents)
        fn += len(expected_intents - routed)

        is_exact = (expected_intents == routed)
        if is_exact:
            exact_intent_matches += 1

        # Slot extraction comparison
        item_slots_passed = True
        for slot_k, expected_val in expected_slots.items():
            total_slots_tested += 1
            actual_val = parsed.get(slot_k)

            if isinstance(expected_val, list):
                # Ingredients or list comparison
                actual_list = actual_val if isinstance(actual_val, list) else []
                # Check if all expected items are in parsed list
                if all(exp in actual_list for exp in expected_val):
                    correct_slots += 1
                else:
                    item_slots_passed = False
            elif isinstance(expected_val, str):
                if actual_val and expected_val.lower() in str(actual_val).lower():
                    correct_slots += 1
                else:
                    item_slots_passed = False
            else:
                if actual_val == expected_val:
                    correct_slots += 1
                else:
                    item_slots_passed = False

        results_detail.append({
            "id": qid,
            "query": query,
            "expected_intents": list(expected_intents),
            "predicted_intents": list(routed),
            "intent_match": is_exact,
            "slots_match": item_slots_passed,
        })

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
    f1 = round(2 * (precision * recall) / (precision + recall), 4) if (precision + recall) > 0 else 1.0
    accuracy = round(exact_intent_matches / total, 4) if total > 0 else 1.0
    slot_accuracy = round(correct_slots / total_slots_tested, 4) if total_slots_tested > 0 else 1.0

    return {
        "category": "intent_routing",
        "total_test_cases": total,
        "exact_match_accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1_score": f1,
        "slot_accuracy": slot_accuracy,
        "passed": accuracy >= 0.90,
        "details": results_detail,
    }


if __name__ == "__main__":
    res = evaluate_intent_and_routing()
    print(json.dumps(res, indent=2))
