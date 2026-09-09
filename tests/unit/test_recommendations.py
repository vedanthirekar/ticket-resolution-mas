from luma.services.recommendations import (
    build_customer_resolution_response,
    build_recommendation_presentation,
)


def _late_cancellation_evidence() -> list[dict[str, object]]:
    return [
        {
            "evidence_type": "appointment_timeline",
            "condition": "present",
            "content": {
                "data": {
                    "appointment": {"scheduled_start": "2026-07-11T17:00:00Z"},
                    "events": [
                        {
                            "event_type": "appointment_cancelled",
                            "initiating_party": "customer",
                            "occurred_at": "2026-07-11T13:00:00Z",
                        }
                    ],
                }
            },
        },
        {
            "evidence_type": "payment",
            "condition": "present",
            "content": {"data": {"payments": [{"captured_amount_cents": 6000}]}},
        },
    ]


def test_late_cancellation_recommendation_uses_plain_language_and_exact_facts() -> None:
    evidence = _late_cancellation_evidence()

    result = build_recommendation_presentation(
        outcome="retain_cancellation_fee",
        supported=True,
        evidence=evidence,
        action_payload=None,
        proposal_rationale="Technical rationale with APPT-CAN-LATE and ISO timestamps.",
        verification_rationale="Verified.",
        next_step="No further action is required.",
    )

    assert result["headline"] == "Keep the $60 cancellation fee"
    assert result["explanation"] == (
        "The customer cancelled the appointment 4 hours before it was scheduled to begin. "
        "Luma requires at least 24 hours' notice to avoid a cancellation fee. "
        "The $60 charge is allowed under the policy."
    )
    assert result["key_facts"] == [
        "Cancelled by customer",
        "4 hours before it was scheduled to begin",
        "$60 charged",
    ]
    assert result["technical_rationale"].startswith("Technical rationale")


def test_late_cancellation_customer_response_answers_the_fee_question() -> None:
    response = build_customer_resolution_response(
        outcome="retain_cancellation_fee",
        evidence=_late_cancellation_evidence(),
        action_payload=None,
        execution_receipt=None,
    )

    assert "$60 cancellation fee" in response
    assert "July 11, 2026 appointment" in response
    assert "4 hours before" in response
    assert "at least 24 hours" in response
    assert "no refund is due" in response
    assert "No account change was required" not in response


def test_no_show_recommendation_uses_the_canonical_terminal_event() -> None:
    result = build_recommendation_presentation(
        outcome="retain_no_show_fee",
        supported=True,
        evidence=[
            {
                "evidence_type": "appointment_timeline",
                "condition": "present",
                "content": {
                    "data": {
                        "appointment": {"scheduled_start": "2026-07-12T17:00:00Z"},
                        "events": [
                            {
                                "event_type": "appointment_marked_no_show",
                                "initiating_party": "customer",
                                "occurred_at": "2026-07-12T17:15:00Z",
                            }
                        ],
                    }
                },
            },
            {
                "evidence_type": "payment",
                "condition": "present",
                "content": {"data": {"payments": [{"captured_amount_cents": 12000}]}},
            },
        ],
        action_payload=None,
        proposal_rationale="The no-show fee is valid.",
        verification_rationale="Verified.",
        next_step="No further action is required.",
    )

    assert result["headline"] == "Keep the $120 no-show fee"
    assert "Marked as a no-show" in result["key_facts"]


def test_authorization_hold_customer_response_explains_capture_status() -> None:
    response = build_customer_resolution_response(
        outcome="explain_authorization_hold",
        evidence=[
            {
                "evidence_type": "payment",
                "condition": "present",
                "content": {
                    "data": {
                        "payments": [
                            {
                                "authorized_amount_cents": 6000,
                                "captured_amount_cents": 0,
                            }
                        ]
                    }
                },
            }
        ],
        action_payload=None,
        execution_receipt=None,
    )

    assert "$60 pending card entry" in response
    assert "authorized but not captured" in response
    assert "temporary authorization hold" in response


def test_failed_verification_does_not_present_the_proposal_as_a_decision() -> None:
    result = build_recommendation_presentation(
        outcome="retain_cancellation_fee",
        supported=False,
        evidence=[],
        action_payload=None,
        proposal_rationale="Retain it.",
        verification_rationale="The cancellation initiator is contradictory.",
        next_step="Review the evidence and continue the investigation.",
    )

    assert result["headline"] == "Human review is required"
    assert "could not be fully verified" in result["explanation"]
    assert result["technical_rationale"] == ("The cancellation initiator is contradictory.")
