import json
from pathlib import Path

import pytest

import luma.simulator as simulator
from luma.simulator import load_tickets, run_simulator


def test_simulator_fixture_is_valid_and_business_linked() -> None:
    fixture = Path(__file__).parents[2] / "simulator" / "tickets.jsonl"
    tickets = load_tickets(fixture)
    assert len(tickets) >= 40
    assert len({ticket.scenario for ticket in tickets}) == len(tickets)
    assert len({ticket.complaint for ticket in tickets}) == len(tickets)
    assert all(ticket.customer_reference.startswith("CUS-") for ticket in tickets)
    assert all(ticket.claimed_category for ticket in tickets)
    assert all(ticket.contact_email == "simulated.customer@example.test" for ticket in tickets)
    assert all(
        internal_prefix not in ticket.complaint
        for ticket in tickets
        for internal_prefix in ("APPT-", "BATT-", "MEM-", "PAY-", "POL-")
    )
    assert all("`" not in ticket.complaint for ticket in tickets)
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


def test_submit_ticket_includes_contact_email(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"public_reference":"CASE-TEST","status":"received"}'

    def fake_urlopen(request: object, timeout: int) -> FakeResponse:
        captured["payload"] = json.loads(request.data)  # type: ignore[attr-defined]
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(simulator, "urlopen", fake_urlopen)
    ticket = simulator.SimulatedTicket(
        scenario="sample",
        customer_reference="CUS-0001",
        claimed_category="other",
        complaint="Please review my case.",
    )

    simulator.submit_ticket("http://127.0.0.1:8000", ticket)

    assert captured["payload"]["contact_email"] == "simulated.customer@example.test"  # type: ignore[index]
