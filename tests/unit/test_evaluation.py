from __future__ import annotations

from luma.evaluation.contracts import EvalObservation
from luma.evaluation.dataset import load_dataset
from luma.evaluation.graders import grade_case, summarize_results


def test_versioned_dataset_expands_to_sixty_cases() -> None:
    dataset = load_dataset()

    assert dataset.dataset_version == "luma_cases_v1"
    assert len(dataset.cases) == 60
    assert len({case.case_id for case in dataset.cases}) == 60
    assert sum(case.split == "development" for case in dataset.cases) == 36
    assert sum(case.split == "held_out" for case in dataset.cases) == 24
    assert {case.test_type for case in dataset.cases} == {
        "happy_path",
        "boundary",
        "counterfactual",
        "adversarial",
        "tool_failure",
    }


def test_deterministic_grader_exposes_exact_failures_and_safety() -> None:
    case = load_dataset().cases[0]
    observation = EvalObservation(
        case_id=case.case_id,
        category=case.expected_category,
        outcome=case.expected_outcome,
        disposition=case.expected_disposition,
        evidence_types=case.required_evidence_types,
        source_references=case.required_source_references,
        policy_references=case.required_policy_references,
        tools_called=case.expected_tools,
        action=case.expected_action.model_dump(exclude_none=True) if case.expected_action else None,
    )
    grade = grade_case(case, observation)
    assert grade.passed

    unsafe = observation.model_copy(
        update={"unauthorized_mutation_count": 1, "action": {"action_type": "refund_payment"}}
    )
    unsafe_grade = grade_case(case, unsafe)
    assert not unsafe_grade.passed
    assert (
        next(metric for metric in unsafe_grade.metrics if metric.name == "action_safety").passed
        is False
    )


def test_aggregate_metrics_use_explicit_denominators() -> None:
    case = load_dataset().cases[0]
    observation = EvalObservation(case_id=case.case_id, disposition="human_investigation")
    grade = grade_case(case, observation)
    summary = summarize_results([case], [observation], [grade])

    assert summary["case_count"] == 1
    assert summary["escalation_precision"] == 0
    assert summary["escalation_recall"] is None
    assert summary["latency_ms"]["p95"] is None
