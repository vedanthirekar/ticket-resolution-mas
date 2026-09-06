from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


class RecommendationPresentation(TypedDict):
    headline: str
    explanation: str
    key_facts: list[str]
    next_step: str
    technical_rationale: str


def _appointment_date(timeline_data: dict[str, Any]) -> str | None:
    appointment = _record(timeline_data.get("appointment"))
    value = appointment.get("scheduled_start")
    if value is None:
        return None
    try:
        scheduled = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return scheduled.strftime("%B %d, %Y").replace(" 0", " ")


def _authorization_amount(payment_data: dict[str, Any]) -> str | None:
    payments = payment_data.get("payments")
    if not isinstance(payments, list):
        return None
    for payment in payments:
        if not isinstance(payment, dict):
            continue
        authorized = payment.get("authorized_amount_cents")
        captured = payment.get("captured_amount_cents")
        if isinstance(authorized, int) and authorized > 0 and captured == 0:
            return _money(authorized)
    return None


def build_customer_resolution_response(
    *,
    outcome: str,
    evidence: list[dict[str, Any]],
    action_payload: dict[str, Any] | None,
    execution_receipt: dict[str, Any] | None,
) -> str:
    """Render a customer-facing resolution from verified structured facts."""
    payment_data = _evidence_data(evidence, "payment")
    timeline_data = _evidence_data(evidence, "appointment_timeline")
    amount = _amount(action_payload, payment_data)
    initiator, notice = _timeline_facts(timeline_data)
    appointment_date = _appointment_date(timeline_data)
    dated_appointment = (
        f"your {appointment_date} appointment" if appointment_date else "your appointment"
    )

    if outcome == "retain_cancellation_fee":
        subject = f"the {amount} cancellation fee" if amount else "the cancellation fee"
        cancellation = (
            f"Our records show that you cancelled {dated_appointment}"
            if initiator == "Customer"
            else f"Our records show that {dated_appointment} was cancelled"
        )
        timing = f" {notice}" if notice else " with less than the required notice"
        return (
            f"We reviewed {subject} for {dated_appointment}. {cancellation}{timing}. "
            "Luma requires at least 24 hours' notice to avoid a cancellation fee. "
            "Based on the verified records and applicable policy, the fee was correctly "
            "charged and no refund is due."
        )

    if outcome == "retain_no_show_fee":
        subject = f"the {amount} no-show fee" if amount else "the no-show fee"
        return (
            f"We reviewed {subject} for {dated_appointment}. The appointment record shows "
            "that you did not attend. Based on the verified record and the applicable "
            "no-show policy, the fee was correctly charged and no refund is due."
        )

    if outcome == "explain_authorization_hold":
        pending_amount = _authorization_amount(payment_data)
        subject = (
            f"the {pending_amount} pending card entry"
            if pending_amount
            else "the pending card entry"
        )
        return (
            f"We reviewed {subject}. Our payment records show that it was authorized but "
            "not captured. It is a temporary authorization hold, not a completed charge, "
            "so there is no captured payment to refund."
        )

    if outcome == "explain_distinct_charges":
        return (
            "We reviewed the charges you reported. The verified records show that they belong "
            "to different completed appointments, so they are not duplicate charges and no "
            "refund is due."
        )

    if outcome == "refund_cancellation_fee":
        party = (initiator or "Provider or Luma").lower()
        subject = f"the {amount} cancellation fee" if amount else "the cancellation fee"
        completed = " The approved refund has been completed." if execution_receipt else ""
        return (
            f"We reviewed {subject} for {dated_appointment}. The records show that the "
            f"appointment was cancelled by the {party}, so the cancellation fee should not "
            f"have been charged.{completed}"
        )

    if outcome == "refund_duplicate_payment":
        subject = f"the {amount} duplicate charge" if amount else "the duplicate charge"
        completed = " The approved refund has been completed." if execution_receipt else ""
        return (
            f"We reviewed {subject}. The verified payment records show that the same "
            "obligation was captured twice, so the additional charge should be refunded."
            f"{completed}"
        )

    if outcome == "restore_duplicate_credit":
        delta = _record(action_payload).get("credit_delta")
        quantity = abs(delta) if isinstance(delta, int) else None
        credit = (
            f"an additional {quantity} membership credit"
            if quantity == 1
            else f"an additional {quantity} membership credits"
            if quantity is not None
            else "an additional membership credit"
        )
        completed = (
            " The approved credit adjustment has been completed." if execution_receipt else ""
        )
        return (
            "We reviewed your membership activity. The verified ledger shows that an extra "
            f"credit was used for the same appointment, so {credit} should be restored.{completed}"
        )

    if outcome == "explain_booking_restriction":
        return (
            "We reviewed the unsuccessful booking attempt. The verified configuration shows "
            "that it was blocked by the location, provider, or service booking rules in effect "
            "at that time. No appointment was created and no account change is required."
        )

    if outcome == "escalate_booking_technical_failure":
        return (
            "We confirmed that the booking attempt failed because of a technical error and did "
            "not create an appointment. The issue requires additional investigation before we "
            "can provide a final resolution."
        )

    return (
        "We could not establish a sufficiently supported automatic resolution from the available "
        "records. The case requires additional investigation."
    )


HEADLINES = {
    "refund_cancellation_fee": "Refund the cancellation fee",
    "retain_cancellation_fee": "Keep the cancellation fee",
    "retain_no_show_fee": "Keep the no-show fee",
    "refund_duplicate_payment": "Refund the duplicate charge",
    "explain_distinct_charges": "The charges are not duplicates",
    "explain_authorization_hold": "Explain the pending authorization",
    "restore_duplicate_credit": "Restore the membership credit",
    "explain_booking_restriction": "Explain why booking was unavailable",
    "escalate_booking_technical_failure": "Send the booking issue for human review",
    "insufficient_grounding": "Human review is required",
}


def _record(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _data(evidence: dict[str, Any]) -> dict[str, Any]:
    outer = _record(evidence.get("content"))
    content = _record(outer.get("content"))
    return _record(content.get("data", outer.get("data")))


def _evidence_data(evidence: list[dict[str, Any]], evidence_type: str) -> dict[str, Any]:
    for item in evidence:
        if item.get("evidence_type") == evidence_type and item.get("condition") == "present":
            return _data(item)
    return {}


def _money(cents: object) -> str | None:
    if not isinstance(cents, int):
        return None
    return f"${cents / 100:,.2f}".replace(".00", "")


def _amount(action_payload: dict[str, Any] | None, payment_data: dict[str, Any]) -> str | None:
    action_amount = _record(action_payload).get("amount_cents")
    if isinstance(action_amount, int):
        return _money(action_amount)
    payments = payment_data.get("payments")
    if not isinstance(payments, list):
        return None
    captured = sum(
        payment.get("captured_amount_cents", 0)
        for payment in payments
        if isinstance(payment, dict) and isinstance(payment.get("captured_amount_cents"), int)
    )
    return _money(captured) if captured else None


def _timeline_facts(timeline_data: dict[str, Any]) -> tuple[str | None, str | None]:
    appointment = _record(timeline_data.get("appointment"))
    events = timeline_data.get("events")
    if not isinstance(events, list):
        return None, None
    terminal = next(
        (
            event
            for event in events
            if isinstance(event, dict)
            and event.get("event_type") in {"appointment_cancelled", "appointment_no_show"}
        ),
        None,
    )
    if terminal is None:
        return None, None
    party = terminal.get("initiating_party")
    initiator = str(party).replace("_", " ").title() if party else None
    try:
        start = datetime.fromisoformat(str(appointment["scheduled_start"]).replace("Z", "+00:00"))
        occurred = datetime.fromisoformat(str(terminal["occurred_at"]).replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError):
        return initiator, None
    hours = (start - occurred).total_seconds() / 3600
    if hours < 0:
        return initiator, None
    formatted = str(int(hours)) if hours.is_integer() else f"{hours:.1f}"
    return initiator, f"{formatted} hours before it was scheduled to begin"


def _with_amount(headline: str, amount: str | None, outcome: str) -> str:
    if not amount:
        return headline
    replacements = {
        "refund_cancellation_fee": f"Refund the {amount} cancellation fee",
        "retain_cancellation_fee": f"Keep the {amount} cancellation fee",
        "retain_no_show_fee": f"Keep the {amount} no-show fee",
        "refund_duplicate_payment": f"Refund the {amount} duplicate charge",
    }
    return replacements.get(outcome, headline)


def _explanation(
    outcome: str,
    *,
    amount: str | None,
    initiator: str | None,
    notice: str | None,
) -> str:
    if outcome == "retain_cancellation_fee":
        timing = f" {notice}." if notice else "."
        return (
            f"The {(initiator or 'customer').lower()} cancelled the appointment{timing} "
            "Luma requires at least 24 hours' notice to avoid a cancellation fee."
            f" The {amount + ' ' if amount else ''}charge is allowed under the policy."
        )
    if outcome == "refund_cancellation_fee":
        party = (initiator or "provider or Luma").lower()
        return (
            f"The appointment was cancelled by the {party}. The customer should not be charged "
            "when the provider or Luma cancels the appointment."
        )
    if outcome == "retain_no_show_fee":
        return (
            "The appointment record shows that the customer did not attend. "
            f"The {amount + ' ' if amount else ''}fee is allowed under the no-show policy."
        )
    if outcome == "refund_duplicate_payment":
        return (
            "The records show that the same obligation was charged twice. "
            "The extra charge should be refunded."
        )
    if outcome == "explain_distinct_charges":
        return "The charges belong to different completed appointments, so no refund is needed."
    if outcome == "explain_authorization_hold":
        return (
            "The payment is only a pending authorization. No money was captured, "
            "so no refund is needed."
        )
    if outcome == "restore_duplicate_credit":
        return (
            "The records show that an extra membership credit was used for the same "
            "appointment. The extra credit should be restored."
        )
    if outcome == "explain_booking_restriction":
        return (
            "The booking request was blocked by the location or service rules in effect "
            "at that time. No account change is needed."
        )
    if outcome == "escalate_booking_technical_failure":
        return "The records show a technical booking failure that cannot be resolved automatically."
    return "The available records do not support a safe automatic decision."


def build_recommendation_presentation(
    *,
    outcome: str,
    supported: bool | None,
    evidence: list[dict[str, Any]],
    action_payload: dict[str, Any] | None,
    proposal_rationale: str,
    verification_rationale: str | None,
    next_step: str,
) -> RecommendationPresentation:
    technical_rationale = proposal_rationale
    if supported is False and verification_rationale:
        technical_rationale = verification_rationale
    if supported is False:
        return {
            "headline": "Human review is required",
            "explanation": (
                "The automated recommendation could not be fully verified. A person needs "
                "to review the evidence before a decision is made."
            ),
            "key_facts": [],
            "next_step": next_step,
            "technical_rationale": technical_rationale,
        }

    payment_data = _evidence_data(evidence, "payment")
    timeline_data = _evidence_data(evidence, "appointment_timeline")
    amount = _amount(action_payload, payment_data)
    initiator, notice = _timeline_facts(timeline_data)
    facts: list[str] = []
    if outcome in {"refund_cancellation_fee", "retain_cancellation_fee"}:
        facts = [
            fact
            for fact in (
                f"Cancelled by {initiator.lower()}" if initiator else None,
                notice,
                f"{amount} charged" if amount else None,
            )
            if fact
        ]
    elif outcome == "retain_no_show_fee":
        facts = ["Marked as a no-show", *([f"{amount} charged"] if amount else [])]
    elif outcome == "refund_duplicate_payment" and amount:
        facts = [f"{amount} refund proposed"]
    elif outcome == "explain_authorization_hold":
        facts = ["No money captured"]
    elif outcome == "restore_duplicate_credit":
        credit_delta = _record(action_payload).get("credit_delta")
        if isinstance(credit_delta, int):
            noun = "credit" if abs(credit_delta) == 1 else "credits"
            facts = [f"Restore {abs(credit_delta)} {noun}"]
    return {
        "headline": _with_amount(
            HEADLINES.get(outcome, "Review the recommendation"), amount, outcome
        ),
        "explanation": _explanation(outcome, amount=amount, initiator=initiator, notice=notice),
        "key_facts": facts,
        "next_step": next_step,
        "technical_rationale": technical_rationale,
    }
