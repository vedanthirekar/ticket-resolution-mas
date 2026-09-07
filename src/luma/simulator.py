from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4


@dataclass(frozen=True, slots=True)
class SimulatedTicket:
    scenario: str
    customer_reference: str
    claimed_category: str
    complaint: str
    contact_email: str = "simulated.customer@example.test"


def load_tickets(path: Path) -> list[SimulatedTicket]:
    tickets: list[SimulatedTicket] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            tickets.append(SimulatedTicket(**payload))
        except (json.JSONDecodeError, TypeError) as error:
            raise ValueError(f"invalid simulator fixture at line {line_number}: {error}") from error
    if not tickets:
        raise ValueError("simulator fixture contains no tickets")
    return tickets


def submit_ticket(api_url: str, ticket: SimulatedTicket) -> dict[str, Any]:
    payload = json.dumps(
        {
            "complaint_text": ticket.complaint,
            "source": "simulator",
            "external_request_key": f"sim-{ticket.scenario}-{uuid4().hex}",
            "claimed_customer_reference": ticket.customer_reference,
            "contact_email": ticket.contact_email,
            "claimed_category": ticket.claimed_category,
        }
    ).encode()
    request = Request(
        f"{api_url.rstrip('/')}/api/cases",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            result: dict[str, Any] = json.loads(response.read())
            return result
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise RuntimeError(f"intake returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"could not reach intake API: {error.reason}") from error


def run_simulator(
    *,
    api_url: str,
    fixture: Path,
    minimum_interval: float,
    maximum_interval: float,
    count: int | None,
) -> None:
    if minimum_interval <= 0 or maximum_interval < minimum_interval:
        raise ValueError("intervals must be positive and maximum must be at least minimum")
    tickets = load_tickets(fixture)
    randomizer = random.SystemRandom()
    sent = 0
    print(f"Simulator active: {len(tickets)} scenarios, {minimum_interval:g}-{maximum_interval:g}s")
    print("Press Ctrl+C to stop. The operations dashboard has no simulator controls.")
    while count is None or sent < count:
        ticket = randomizer.choice(tickets)
        result = submit_ticket(api_url, ticket)
        sent += 1
        print(
            f"[{sent}] submitted {ticket.scenario}: "
            f"{result.get('public_reference', 'unknown')} ({result.get('status', 'unknown')})"
        )
        if count is None or sent < count:
            time.sleep(randomizer.uniform(minimum_interval, maximum_interval))


def main() -> None:
    default_fixture = Path(__file__).resolve().parents[2] / "simulator" / "tickets.jsonl"
    parser = argparse.ArgumentParser(description="Submit realistic Luma cases at random intervals")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument("--fixture", type=Path, default=default_fixture)
    parser.add_argument("--min-interval", type=float, default=10)
    parser.add_argument("--max-interval", type=float, default=20)
    parser.add_argument("--count", type=int, help="stop after N cases; default runs until Ctrl+C")
    args = parser.parse_args()
    try:
        run_simulator(
            api_url=args.api_url,
            fixture=args.fixture,
            minimum_interval=args.min_interval,
            maximum_interval=args.max_interval,
            count=args.count,
        )
    except KeyboardInterrupt:
        print("\nSimulator stopped.")


if __name__ == "__main__":
    main()
