"""Pytest Regression test suite for Evals Benchmarks."""
import pytest
from evals.evaluators.eval_intent import evaluate_intent_and_routing
from evals.evaluators.eval_trajectory import evaluate_agent_trajectories
from evals.evaluators.eval_reflection import evaluate_reflection_matrix
from evals.evaluators.eval_llm_judge import evaluate_synthesis_quality
from evals.evaluators.eval_adversarial import evaluate_adversarial_and_edge_cases
from evals.evaluators.eval_negative import evaluate_negative_constraints
from evals.evaluators.eval_multitool import evaluate_multitool_orchestration


def test_intent_routing_benchmark():
    """Verify Intent Classification and Slot Extraction achieve >= 90% accuracy."""
    res = evaluate_intent_and_routing()
    assert res["exact_match_accuracy"] >= 0.90, f"Intent accuracy {res['exact_match_accuracy']} < 0.90"
    assert res["f1_score"] >= 0.90, f"Intent F1 {res['f1_score']} < 0.90"
    assert res["slot_accuracy"] >= 0.85, f"Slot accuracy {res['slot_accuracy']} < 0.85"


def test_agent_trajectory_benchmark():
    """Verify ReAct Agentic Loop Tool Selection achieves >= 90% accuracy."""
    res = evaluate_agent_trajectories()
    assert res["overall_accuracy"] >= 0.90, f"Trajectory accuracy {res['overall_accuracy']} < 0.90"
    assert res["tool_selection_accuracy"] >= 0.90, f"Tool accuracy {res['tool_selection_accuracy']} < 0.90"
    assert res["step_efficiency_rate"] >= 0.90, f"Efficiency rate {res['step_efficiency_rate']} < 0.90"


def test_reflection_matrix_benchmark():
    """Verify Cross-Domain Reflection consistency rules achieve >= 95% pass rate."""
    res = evaluate_reflection_matrix()
    assert res["accuracy"] >= 0.95, f"Reflection accuracy {res['accuracy']} < 0.95"


def test_synthesis_quality_judge_benchmark():
    """Verify response synthesis quality and faithfulness score >= 4.0/5.0."""
    res = evaluate_synthesis_quality(use_llm_judge=False)
    assert res["avg_faithfulness"] >= 4.0, f"Faithfulness {res['avg_faithfulness']} < 4.0"
    assert res["avg_relevance"] >= 3.5, f"Relevance {res['avg_relevance']} < 3.5"


def test_adversarial_and_edge_cases_benchmark():
    """Verify Adversarial and Out-of-the-Box Edge Cases achieve >= 85% accuracy."""
    res = evaluate_adversarial_and_edge_cases()
    assert res["overall_accuracy"] >= 0.85, f"Adversarial accuracy {res['overall_accuracy']} < 0.85"
    assert res["extreme_reflection_accuracy"] == 1.0, f"Extreme reflection {res['extreme_reflection_accuracy']} < 1.0"


def test_negative_constraints_benchmark():
    """Verify Negative Constraints and Excluded Tools achieve >= 90% accuracy."""
    res = evaluate_negative_constraints()
    assert res["accuracy"] >= 0.90, f"Negative constraints accuracy {res['accuracy']} < 0.90"


def test_multitool_orchestration_benchmark():
    """Verify Complex Multi-Tool Orchestration achieves >= 80% accuracy."""
    res = evaluate_multitool_orchestration()
    assert res["accuracy"] >= 0.80, f"Multi-tool accuracy {res['accuracy']} < 0.80"


