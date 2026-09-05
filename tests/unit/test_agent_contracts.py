from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from luma.agents.contracts import (
    EvidenceRecord,
    InvestigationPlanOutput,
    OperationalCall,
    PolicyAssessmentOutput,
    ResolutionProposalOutput,
)
from luma.agents.graph import _evidence_gate, _material_event_date


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


def test_deterministic_requirements_cannot_be_weakened_by_plan() -> None:
    gate = _evidence_gate(_plan(required_evidence_types=[]), [_evidence("customer_identity")])

    assert gate.sufficient is False
    assert gate.missing_evidence == ["appointment_timeline", "payment"]


def test_plan_cannot_extend_deterministic_requirements() -> None:
    gate = _evidence_gate(
        _plan(required_evidence_types=["accepted_transfer"]),
        [
            _evidence("customer_identity"),
            _evidence("appointment_timeline"),
            _evidence("payment"),
        ],
    )

    assert gate.sufficient is True
    assert gate.missing_evidence == []


def test_authoritative_event_date_overrides_planner_guess() -> None:
    derived = _material_event_date(
        _plan(material_event_date=date(2024, 1, 1)),
        [{"content": {"data": {"appointment": {"scheduled_start": "2026-08-20T17:00:00Z"}}}}],
    )

    assert derived == date(2026, 8, 20)


def test_contradiction_forces_human_investigation() -> None:
    gate = _evidence_gate(
        _plan(),
        [
            _evidence("customer_identity"),
            _evidence("appointment_timeline", "contradictory"),
            _evidence("payment"),
        ],
    )

    assert gate.sufficient is False
    assert gate.reason_code == "conflicting_operational_evidence"


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
        supplemental_call=OperationalCall(
            tool_name="get_customer_appointments",
            arguments={},
            purpose="Unnecessary extra lookup.",
        ),
    )

    assert assessment.supplemental_call is None
