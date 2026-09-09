# Customer ticket fixture

`tickets.jsonl` supplies demo traffic to the standalone simulator. Each non-empty
line is one JSON object with four required fields:

- `scenario`: a unique internal label used only in simulator logs.
- `customer_reference`: the seeded customer whose records contain the relevant
  evidence. This is intake metadata, not part of the customer's message.
- `claimed_category`: the category selected by the customer at intake.
- `complaint`: the customer-visible message shown in the case queue.

Simulator submissions use `simulated.customer@example.test` as the contact email by
default so resolved cases produce an email draft on the operations dashboard. A
fixture row can optionally set `contact_email` to override that address.

## Writing a good demo ticket

Write the complaint in customer language. Include the details a real customer is
likely to know, such as the date, location, service, provider, amount, or whether a
card entry is pending. Vary tone and detail: some customers are concise, some give
context, and some misunderstand what happened.

Do not place fixture identifiers such as `APPT-*`, `BATT-*`, `MEM-*`, `PAY-*`, or
`POL-*` in the complaint. Do not tell the agent which policy version to use, which
database records to inspect, what conclusion to reach, or how to bypass approval.
Those details belong in evaluation cases, not ordinary customer messages.

Every resolvable demo ticket should map to evidence seeded for its
`customer_reference`. Canonical appointments, payments, membership activity, and
booking attempts are defined in
`synthetic_enterprise/luma_enterprise/builder.py`. A deliberately unsupported ticket
may use the `other` category to demonstrate safe routing to a person.

After editing the fixture, run:

```powershell
uv run pytest tests/unit/test_simulator.py -q
```

The simulator reads the file when it starts, so restart an already-running simulator
to load changes. No database reset or reseed is required.
