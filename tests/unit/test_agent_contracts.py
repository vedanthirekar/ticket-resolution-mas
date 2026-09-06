from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from luma.agents.contracts import (
    EvidenceRecord,
    GetCustomerAppointmentsCall,
    InvestigationDecisionOutput,
    InvestigationPlanOutput,
    PolicyAssessmentOutput,
    ResolutionProposalOutput,
)
from luma.agents.graph import _evidence_coverage, _material_event_date, _preverify


def _plan(**overrides):
    values = {
        "category": "cancellation_fee_dispute",
        "material_event_date": date(2026, 8, 20),
        "required_evidence_types": [],
        "investigation_objectives": ["Establish authoritative cancellation and payment facts."],
        "policy_query": "provider cancellation fee",
        "rationale": "Investigate the cancellation and charge.",
    }
    values.update(overrides)
    return InvestigationPlanOutput.model_validate(values)


def _evidence(evidence_type: str, condition: str = "present") -> EvidenceRecord:
    return EvidenceRecord.model_validate(
        {
            "evidence_type": evidence_type,
            "condition": condition,
            "tool_name": "test_tool",
        }
    )


def test_diagnostic_requirements_cannot_be_weakened_by_plan() -> None:
    coverage = _evidence_coverage(
        _plan(required_evidence_types=[]), [_evidence("customer_identity")]
    )

    assert coverage.complete is False
    assert coverage.missing_evidence == ["appointment_timeline", "payment"]


def test_plan_cannot_extend_diagnostic_requirements() -> None:
    coverage = _evidence_coverage(
        _plan(required_evidence_types=["accepted_transfer"]),
        [
            _evidence("customer_identity"),
            _evidence("appointment_timeline"),
            _evidence("payment"),
        ],
    )

    assert coverage.complete is True
    assert coverage.missing_evidence == []


def test_authoritative_event_date_overrides_planner_guess() -> None:
    derived = _material_event_date(
        _plan(material_event_date=date(2024, 1, 1)),
        [{"content": {"data": {"appointment": {"scheduled_start": "2026-08-20T17:00:00Z"}}}}],
    )

    assert derived == date(2026, 8, 20)


def test_contradiction_is_reported_in_coverage() -> None:
    coverage = _evidence_coverage(
        _plan(),
        [
            _evidence("customer_identity"),
            _evidence("appointment_timeline", "contradictory"),
            _evidence("payment"),
        ],
    )

    assert coverage.complete is False
    assert coverage.contradictions == ["appointment_timeline"]


def test_mutation_cannot_be_marked_auto_resolve() -> None:
    with pytest.raises(ValidationError, match="mutations require human approval"):
        ResolutionProposalOutput(
            outcome="refund_cancellation_fee",
            disposition="auto_resolve",
            rationale="Refund is supported.",
            action_payload={
                "action_type": "refund_payment",
                "payment_reference": "PAY-1",
                "amount_cents": 8000,
                "reason_code": "provider_cancelled_fee",
            },
            evidence_references=[],
            policy_references=[],
        )


def test_unneeded_policy_supplemental_call_is_discarded() -> None:
    assessment = PolicyAssessmentOutput(
        applicable=True,
        selected_section_ids=["POL-CAN-v2#4.1"],
        rule_summary="Provider cancellation fee is refundable.",
        missing_evidence_types=[],
        supplemental_call=GetCustomerAppointmentsCall(
            tool_name="get_customer_appointments",
            arguments={},
            purpose="Unnecessary extra lookup.",
        ),
    )

    assert assessment.supplemental_call is None


@pytest.mark.parametrize(
    ("tool_name", "arguments", "missing_field"),
    [
        ("get_appointment_timeline", {}, "appointment_reference"),
        ("get_appointment_payments", {}, "appointment_reference"),
        ("get_booking_attempt_evidence", {}, "booking_attempt_reference"),
        ("get_membership_evidence", {}, "as_of"),
    ],
)
def test_exact_detail_calls_require_typed_arguments(
    tool_name: str, arguments: dict[str, object], missing_field: str
) -> None:
    with pytest.raises(ValidationError, match=missing_field):
        InvestigationDecisionOutput.model_validate(
            {
                "complete": False,
                "next_call": {
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "purpose": "Retrieve exact authoritative evidence.",
                },
                "rationale": "The exact record is required.",
            }
        )


def test_action_target_and_value_must_be_bound_in_one_evidence_record() -> None:
    result = _preverify(
        {
            "proposal": {
                "outcome": "refund_cancellation_fee",
                "disposition": "human_approval",
                "rationale": "Refund the captured fee.",
                "action_payload": {
                    "action_type": "refund_payment",
                    "payment_reference": "PAY-1",
                    "amount_cents": 8000,
                    "reason_code": "provider_cancelled_fee",
                },
                "evidence_references": ["PAY-1"],
                "policy_references": ["POL-CAN-v2#4.1"],
            },
            "policy_assessment": {
                "applicable": True,
                "selected_section_ids": ["POL-CAN-v2#4.1"],
                "rule_summary": "Provider cancellation fees are refundable.",
            },
            "evidence": [
                {"condition": "present", "content": {"payment_reference": "PAY-1"}},
                {"condition": "present", "content": {"amount_cents": 8000}},
            ],
        }
    )

    assert result["passed"] is False
    assert "action_target_value_not_bound_in_evidence" in result["failure_reasons"]


def test_action_is_rejected_when_any_authoritative_evidence_is_unavailable() -> None:
    result = _preverify(
        {
            "proposal": {
                "outcome": "refund_cancellation_fee",
                "disposition": "human_approval",
                "rationale": "Refund the captured fee.",
                "action_payload": {
                    "action_type": "refund_payment",
                    "payment_reference": "PAY-1",
                    "amount_cents": 8000,
                    "reason_code": "provider_cancelled_fee",
                },
                "evidence_references": ["PAY-1"],
                "policy_references": ["POL-CAN-v2#4.1"],
            },
            "policy_assessment": {
                "applicable": True,
                "selected_section_ids": ["POL-CAN-v2#4.1"],
                "rule_summary": "Provider cancellation fees are refundable.",
            },
            "evidence": [
                {
                    "condition": "unavailable",
                    "content": {"payment_reference": "PAY-1", "amount_cents": 8000},
                }
            ],
        }
    )

    assert result["passed"] is False
    assert "action_evidence_unreliable" in result["failure_reasons"]
