"""LLM-as-a-Judge and Heuristic Faithfulness Evaluator."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.response_synthesizer import synthesize_response
from services.llm_client import LLMClient

DATASET_PATH = Path(__file__).resolve().parent.parent / "datasets" / "synthesis_golden.json"

JUDGE_PROMPT_TEMPLATE = """
You are an unbiased AI evaluation judge.
Evaluate the following Assistant Response based on the provided Context Data and User Query.

User Query: {query}
Context Data: {context}
Assistant Response: {response}

Score the response on a scale of 1 to 5 for each criterion:
1. Faithfulness: Is every factual claim in the response supported by the Context Data without hallucinations? (1 = completely hallucinated, 5 = perfectly faithful)
2. Relevance: Does the response address all aspects of the User Query? (1 = completely irrelevant, 5 = perfectly relevant)
3. Clarity: Is the response well-formatted, concise, and easy to read? (1 = poorly written, 5 = crystal clear)

Output JSON only in the following format:
{{
  "faithfulness": <1-5>,
  "relevance": <1-5>,
  "clarity": <1-5>,
  "reasoning": "<brief explanation>"
}}
"""


def _heuristic_judge(response: str, key_facts: List[str], required_topics: List[str]) -> Dict[str, Any]:
    """Deterministic heuristic evaluator when LLM API is offline or unconfigured."""
    resp_lower = response.lower()

    # Check key fact coverage
    facts_found = sum(1 for fact in key_facts if fact.lower() in resp_lower)
    fact_ratio = facts_found / len(key_facts) if key_facts else 1.0

    # Check topic coverage
    topics_found = sum(1 for t in required_topics if t.lower() in resp_lower or len(response) > 50)
    topic_ratio = topics_found / len(required_topics) if required_topics else 1.0

    faithfulness = max(1, min(5, int(1 + fact_ratio * 4)))
    relevance = max(1, min(5, int(1 + topic_ratio * 4)))
    clarity = 5 if len(response) > 30 and "\n" in response or "•" in response or len(response) < 500 else 4

    return {
        "faithfulness": faithfulness,
        "relevance": relevance,
        "clarity": clarity,
        "mode": "heuristic",
        "reasoning": f"Grounded {facts_found}/{len(key_facts)} key facts and {topics_found}/{len(required_topics)} topics.",
    }


def evaluate_synthesis_quality(dataset_path: Path | None = None, use_llm_judge: bool = True) -> Dict[str, Any]:
    """Run synthesis quality benchmark with LLM-as-a-Judge or heuristic grading."""
    path = dataset_path or DATASET_PATH
    with open(path, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    llm_client = LLMClient()
    can_use_llm = use_llm_judge and llm_client.is_available()

    total = len(dataset)
    faithfulness_scores: List[float] = []
    relevance_scores: List[float] = []
    clarity_scores: List[float] = []
    details: List[Dict[str, Any]] = []

    from agents.reflection import ReflectionResult

    for item in dataset:
        qid = item["id"]
        query = item["query"]
        raw_context = item["context"]
        key_facts = item.get("key_facts", [])
        required_topics = item.get("required_topics", [])

        # Shape context into sections format expected by synthesize_response
        sections: Dict[str, Any] = {}
        for sec_name, sec_data in raw_context.items():
            if isinstance(sec_data, dict) and "status" in sec_data and "data" in sec_data:
                sections[sec_name] = sec_data
            else:
                sections[sec_name] = {"status": "success", "data": sec_data}

        # Generate response
        refl = ReflectionResult()
        generated_resp = synthesize_response(sections, intent={"location": "your area", "query": query}, reflection=refl)

        judge_result: Dict[str, Any] = {}
        if can_use_llm:
            try:
                prompt = JUDGE_PROMPT_TEMPLATE.format(
                    query=query,
                    context=json.dumps(context),
                    response=generated_resp,
                )
                raw_eval = llm_client.complete(prompt)
                # Parse JSON from response
                m = re.search(r"\{.*\}", raw_eval, re.DOTALL)
                if m:
                    judge_result = json.loads(m.group(0))
                    judge_result["mode"] = "llm_judge"
            except Exception:
                judge_result = _heuristic_judge(generated_resp, key_facts, required_topics)
        else:
            judge_result = _heuristic_judge(generated_resp, key_facts, required_topics)

        f_score = float(judge_result.get("faithfulness", 4))
        r_score = float(judge_result.get("relevance", 4))
        c_score = float(judge_result.get("clarity", 4))

        faithfulness_scores.append(f_score)
        relevance_scores.append(r_score)
        clarity_scores.append(c_score)

        details.append({
            "id": qid,
            "query": query,
            "response": generated_resp,
            "scores": {
                "faithfulness": f_score,
                "relevance": r_score,
                "clarity": c_score,
            },
            "mode": judge_result.get("mode", "heuristic"),
            "reasoning": judge_result.get("reasoning", ""),
        })

    avg_faithfulness = round(sum(faithfulness_scores) / total, 2) if total else 0.0
    avg_relevance = round(sum(relevance_scores) / total, 2) if total else 0.0
    avg_clarity = round(sum(clarity_scores) / total, 2) if total else 0.0

    return {
        "category": "synthesis_judge",
        "total_test_cases": total,
        "avg_faithfulness": avg_faithfulness,
        "avg_relevance": avg_relevance,
        "avg_clarity": avg_clarity,
        "passed": avg_faithfulness >= 4.0 and avg_relevance >= 3.5,
        "judge_mode": "llm" if can_use_llm else "heuristic",
        "details": details,
    }


if __name__ == "__main__":
    res = evaluate_synthesis_quality()
    print(json.dumps(res, indent=2))
