from pathlib import Path

import pytest

from luma.simulator import load_tickets, run_simulator


def test_simulator_fixture_is_valid_and_business_linked() -> None:
    fixture = Path(__file__).parents[2] / "simulator" / "tickets.jsonl"
    tickets = load_tickets(fixture)
    assert len(tickets) == 31
    assert len({ticket.scenario for ticket in tickets}) == len(tickets)
    assert all(ticket.customer_reference.startswith("CUS-") for ticket in tickets)
    assert all(ticket.claimed_category for ticket in tickets)
    assert any("APPT-" not in ticket.complaint for ticket in tickets)
    assert {ticket.claimed_category for ticket in tickets} == {
        "duplicate_payment",
        "cancellation_fee_dispute",
        "missing_appointment",
        "membership_credits",
        "online_booking_unavailable",
        "other",
    }


def test_simulator_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError, match="intervals"):
        run_simulator(
            api_url="http://127.0.0.1:8000",
            fixture=Path("unused"),
            minimum_interval=20,
            maximum_interval=10,
            count=0,
        )
