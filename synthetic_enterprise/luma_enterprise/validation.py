from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from luma.db.base import Base


@dataclass(frozen=True, slots=True)
class ValidationReport:
    checks: dict[str, bool]
    expected_anomalies: dict[str, bool]
    row_counts: dict[str, int]
    checksums: dict[str, str]

    @property
    def passed(self) -> bool:
        return all(self.checks.values()) and all(self.expected_anomalies.values())

    def summary(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks_passed": sum(self.checks.values()),
            "checks_total": len(self.checks),
            "expected_anomalies_verified": sum(self.expected_anomalies.values()),
            "expected_anomalies_total": len(self.expected_anomalies),
            "failed_checks": [name for name, passed in self.checks.items() if not passed],
            "missing_expected_anomalies": [
                name for name, found in self.expected_anomalies.items() if not found
            ],
        }


async def _scalar_int(
    session: AsyncSession, sql: str, parameters: dict[str, Any] | None = None
) -> int:
    result = await session.execute(text(sql), parameters or {})
    return int(result.scalar_one())


async def _row_counts_and_checksums(
    session: AsyncSession,
) -> tuple[dict[str, int], dict[str, str]]:
    row_counts: dict[str, int] = {}
    checksums: dict[str, str] = {}
    tables = sorted(
        (
            table
            for table in Base.metadata.sorted_tables
            if table.schema in {"business", "knowledge"}
        ),
        key=lambda table: (table.schema or "", table.name),
    )
    for table in tables:
        qualified = f'"{table.schema}"."{table.name}"'
        count = await _scalar_int(session, f"SELECT count(*) FROM {qualified}")
        checksum_result = await session.execute(
            text(
                "SELECT md5(coalesce(string_agg((to_jsonb(t) - 'created_at' - 'updated_at' "
                "- 'recorded_at')::text, '' ORDER BY id::text), '')) "
                f"FROM {qualified} AS t"
            )
        )
        row_counts[f"{table.schema}.{table.name}"] = count
        checksums[f"{table.schema}.{table.name}"] = str(checksum_result.scalar_one())
    return row_counts, checksums


async def validate_dataset(session: AsyncSession) -> ValidationReport:
    checks: dict[str, bool] = {}
    expected_anomalies: dict[str, bool] = {}

    checks["entity_counts"] = (
        await _scalar_int(session, "SELECT count(*) FROM business.locations") == 3
        and await _scalar_int(session, "SELECT count(*) FROM business.employees") == 15
        and await _scalar_int(session, "SELECT count(*) FROM business.services") == 25
        and await _scalar_int(session, "SELECT count(*) FROM business.customers") == 300
        and await _scalar_int(session, "SELECT count(*) FROM business.appointments") == 2000
        and await _scalar_int(session, "SELECT count(*) FROM business.memberships") == 150
    )
    checks["appointment_event_scale"] = (
        await _scalar_int(session, "SELECT count(*) FROM business.appointment_events") >= 3000
    )
    checks["public_references_unique"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT public_reference FROM business.appointments GROUP BY 1 HAVING count(*) > 1
                UNION ALL
                SELECT public_reference FROM business.payments GROUP BY 1 HAVING count(*) > 1
                UNION ALL
                SELECT public_reference FROM business.memberships GROUP BY 1 HAVING count(*) > 1
            ) AS duplicates
            """,
        )
        == 0
    )
    checks["provider_qualification"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments AS a
            LEFT JOIN business.employee_services AS es
              ON es.employee_id = a.employee_id
             AND es.service_id = a.service_id
             AND es.valid_from <= a.scheduled_start::date
             AND (es.valid_through IS NULL OR es.valid_through >= a.scheduled_start::date)
            WHERE es.id IS NULL
            """,
        )
        == 0
    )
    checks["provider_location_assignment"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments AS a
            LEFT JOIN business.employee_locations AS el
              ON el.employee_id = a.employee_id
             AND el.location_id = a.location_id
             AND el.valid_from <= a.scheduled_start::date
             AND (el.valid_through IS NULL OR el.valid_through >= a.scheduled_start::date)
            WHERE el.id IS NULL
            """,
        )
        == 0
    )
    checks["appointments_within_provider_schedule"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            WHERE NOT EXISTS (
                SELECT 1 FROM business.employee_schedules s
                WHERE s.employee_id = a.employee_id
                  AND s.location_id = a.location_id
                  AND s.schedule_type = 'available'
                  AND s.starts_at <= a.scheduled_start
                  AND s.ends_at >= a.scheduled_end
            )
            """,
        )
        == 0
    )
    checks["appointments_within_location_hours"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            JOIN business.locations l ON l.id = a.location_id
            WHERE NOT EXISTS (
                SELECT 1 FROM business.location_business_hours h
                WHERE h.location_id = a.location_id
                  AND h.day_of_week = extract(
                        isodow FROM (a.scheduled_start AT TIME ZONE l.timezone)
                      )::int - 1
                  AND h.opens_at <= (a.scheduled_start AT TIME ZONE l.timezone)::time
                  AND h.closes_at >= (a.scheduled_end AT TIME ZONE l.timezone)::time
                  AND h.valid_from <= (a.scheduled_start AT TIME ZONE l.timezone)::date
                  AND (
                    h.valid_through IS NULL
                    OR h.valid_through >= (a.scheduled_start AT TIME ZONE l.timezone)::date
                  )
            )
            """,
        )
        == 0
    )
    checks["appointment_duration_matches_quote"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            JOIN business.services s ON s.id = a.service_id
            WHERE extract(epoch FROM (a.scheduled_end - a.scheduled_start)) / 60
                  <> s.duration_minutes
            """,
        )
        == 0
    )
    checks["providers_not_double_booked"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            JOIN business.appointments b
              ON a.employee_id = b.employee_id AND a.id < b.id
             AND tstzrange(a.scheduled_start, a.scheduled_end, '[)')
                 && tstzrange(b.scheduled_start, b.scheduled_end, '[)')
            WHERE a.status NOT IN ('cancelled') AND b.status NOT IN ('cancelled')
            """,
        )
        == 0
    )
    checks["appointment_state_events_reconcile"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments AS a
            WHERE a.public_reference <> 'APPT-MISSING-EVENT'
              AND (
                (a.status = 'completed' AND NOT EXISTS (
                    SELECT 1 FROM business.appointment_events e
                    WHERE e.appointment_id = a.id AND e.event_type = 'service_completed'
                ))
                OR (a.status = 'cancelled' AND NOT EXISTS (
                    SELECT 1 FROM business.appointment_events e
                    WHERE e.appointment_id = a.id AND e.event_type = 'appointment_cancelled'
                ))
                OR (a.status = 'no_show' AND NOT EXISTS (
                    SELECT 1 FROM business.appointment_events e
                    WHERE e.appointment_id = a.id AND e.event_type = 'appointment_marked_no_show'
                ))
              )
            """,
        )
        == 0
    )
    checks["actor_and_initiator_are_independent"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM business.appointment_events
            WHERE actor_type = 'employee' AND initiating_party = 'customer'
            """,
        )
        > 0
    )
    checks["capture_not_above_authorization"] = (
        await _scalar_int(
            session,
            "SELECT count(*) FROM business.payments "
            "WHERE captured_amount_cents > authorized_amount_cents",
        )
        == 0
    )
    checks["refunds_not_above_capture"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT p.id
                FROM business.payments p
                LEFT JOIN business.refunds r ON r.payment_id = p.id AND r.status = 'succeeded'
                GROUP BY p.id, p.captured_amount_cents
                HAVING coalesce(sum(r.amount_cents), 0) > p.captured_amount_cents
            ) invalid
            """,
        )
        == 0
    )
    checks["payment_projection_reconciles"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT p.id
                FROM business.payments p
                LEFT JOIN business.refunds r ON r.payment_id = p.id AND r.status = 'succeeded'
                GROUP BY p.id, p.refunded_amount_cents
                HAVING coalesce(sum(r.amount_cents), 0) <> p.refunded_amount_cents
            ) invalid
            """,
        )
        == 0
    )
    checks["payment_states_match_amounts"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM business.payments
            WHERE (status IN ('captured', 'partially_refunded', 'refunded')
                   AND captured_amount_cents <= 0)
               OR (status IN ('created', 'authorized', 'voided', 'failed')
                   AND captured_amount_cents <> 0)
               OR (status = 'authorized' AND authorized_amount_cents <= 0)
               OR (status = 'refunded' AND refunded_amount_cents <> captured_amount_cents)
               OR (status = 'partially_refunded'
                   AND (refunded_amount_cents <= 0
                        OR refunded_amount_cents >= captured_amount_cents))
            """,
        )
        == 0
    )
    checks["authorization_hold_is_not_a_capture"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            JOIN business.invoices i ON i.appointment_id = a.id
            JOIN business.payments p ON p.invoice_id = i.id
            WHERE a.public_reference = 'APPT-AUTH-HOLD'
              AND p.status = 'authorized'
              AND p.authorized_amount_cents = 6000
              AND p.captured_amount_cents = 0
            """,
        )
        == 1
    )
    checks["similar_payments_have_distinct_obligations"] = (
        await _scalar_int(
            session,
            """
            SELECT count(DISTINCT p.obligation_reference)
            FROM business.appointments a
            JOIN business.invoices i ON i.appointment_id = a.id
            JOIN business.payments p ON p.invoice_id = i.id
            WHERE a.public_reference IN ('APPT-DISTINCT-A', 'APPT-DISTINCT-B')
              AND p.captured_amount_cents = 12000
            """,
        )
        == 2
    )
    checks["membership_balances_nonnegative"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT membership_id, sum(credit_delta) AS balance
                FROM business.membership_ledger GROUP BY membership_id
            ) balances WHERE balance < 0
            """,
        )
        == 0
    )
    checks["membership_allocations_reconcile"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT ml.id,
                       -ml.credit_delta AS consumed,
                       coalesce(sum(a.quantity), 0) AS allocated
                FROM business.membership_ledger ml
                LEFT JOIN business.membership_credit_allocations a
                  ON a.consumption_entry_id = ml.id
                WHERE ml.entry_type = 'consume'
                GROUP BY ml.id, ml.credit_delta
                HAVING -ml.credit_delta <> coalesce(sum(a.quantity), 0)
            ) invalid
            """,
        )
        == 0
    )
    checks["membership_expirations_reference_grants"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.membership_ledger e
            LEFT JOIN business.membership_ledger g ON g.id = e.related_entry_id
            WHERE e.entry_type = 'expire' AND (g.id IS NULL OR g.entry_type <> 'grant')
            """,
        )
        == 0
    )
    checks["membership_allocations_are_temporally_eligible"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.membership_credit_allocations a
            JOIN business.membership_ledger c ON c.id = a.consumption_entry_id
            JOIN business.membership_ledger g ON g.id = a.grant_entry_id
            WHERE c.entry_type <> 'consume'
               OR g.entry_type <> 'grant'
               OR c.membership_id <> g.membership_id
               OR g.effective_at > c.effective_at
               OR g.expires_at <= c.effective_at
            """,
        )
        == 0
    )
    checks["policy_versions_nonoverlapping"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM knowledge.policy_versions a
            JOIN knowledge.policy_versions b
              ON a.policy_document_id = b.policy_document_id AND a.id < b.id
             AND daterange(
                    a.effective_from,
                    coalesce(a.effective_through + 1, 'infinity'::date),
                    '[)'
                 ) && daterange(
                    b.effective_from,
                    coalesce(b.effective_through + 1, 'infinity'::date),
                    '[)'
                 )
            """,
        )
        == 0
    )
    checks["policy_supersession_valid"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM knowledge.policy_versions current
            LEFT JOIN knowledge.policy_versions prior ON prior.id = current.supersedes_version_id
            WHERE current.version > 1
              AND (prior.id IS NULL OR prior.policy_document_id <> current.policy_document_id
                   OR prior.version <> current.version - 1)
            """,
        )
        == 0
    )
    checks["policy_boundary_selects_one_version"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM knowledge.policy_versions pv
            JOIN knowledge.policy_documents pd ON pd.id = pv.policy_document_id
            WHERE pd.policy_id = 'POL-CAN'
              AND DATE '2025-06-30' BETWEEN pv.effective_from
                  AND coalesce(pv.effective_through, 'infinity'::date)
            """,
        )
        == 1
        and await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM knowledge.policy_versions pv
            JOIN knowledge.policy_documents pd ON pd.id = pv.policy_document_id
            WHERE pd.policy_id = 'POL-CAN'
              AND DATE '2025-07-01' BETWEEN pv.effective_from
                  AND coalesce(pv.effective_through, 'infinity'::date)
            """,
        )
        == 1
    )
    checks["policy_boundary_selects_expected_versions"] = (
        await _scalar_int(
            session,
            """
            SELECT sum(pv.version)
            FROM knowledge.policy_versions pv
            JOIN knowledge.policy_documents pd ON pd.id = pv.policy_document_id
            WHERE pd.policy_id = 'POL-CAN'
              AND DATE '2025-06-30' BETWEEN pv.effective_from
                  AND coalesce(pv.effective_through, 'infinity'::date)
            """,
        )
        == 1
        and await _scalar_int(
            session,
            """
            SELECT sum(pv.version)
            FROM knowledge.policy_versions pv
            JOIN knowledge.policy_documents pd ON pd.id = pv.policy_document_id
            WHERE pd.policy_id = 'POL-CAN'
              AND DATE '2025-07-01' BETWEEN pv.effective_from
                  AND coalesce(pv.effective_through, 'infinity'::date)
            """,
        )
        == 2
    )
    checks["booking_canonical_reasons_present"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM business.booking_attempts
            WHERE public_reference IN (
                'BATT-PROVIDER-OVERRIDE', 'BATT-NO-QUALIFICATION',
                'BATT-OUTSIDE-SCHEDULE', 'BATT-LOCATION-CLOSED',
                'BATT-TECHNICAL-FAILURE'
            ) AND reason_code IS NOT NULL
            """,
        )
        == 5
    )
    checks["booking_provider_override_is_explainable"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.booking_attempts a
            JOIN business.employee_booking_settings s
              ON s.employee_id = a.requested_employee_id
             AND s.service_id = a.service_id
            WHERE a.public_reference = 'BATT-PROVIDER-OVERRIDE'
              AND s.online_enabled = false
              AND s.effective_from <= a.requested_start::date
              AND (s.effective_through IS NULL OR s.effective_through >= a.requested_start::date)
            """,
        )
        == 1
    )
    checks["booking_qualification_failure_is_explainable"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.booking_attempts a
            WHERE a.public_reference = 'BATT-NO-QUALIFICATION'
              AND NOT EXISTS (
                  SELECT 1 FROM business.employee_services es
                  WHERE es.employee_id = a.requested_employee_id
                    AND es.service_id = a.service_id
              )
            """,
        )
        == 1
    )
    checks["booking_schedule_failure_is_explainable"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.booking_attempts a
            JOIN business.services service ON service.id = a.service_id
            WHERE a.public_reference = 'BATT-OUTSIDE-SCHEDULE'
              AND NOT EXISTS (
                  SELECT 1 FROM business.employee_schedules s
                  WHERE s.employee_id = a.requested_employee_id
                    AND s.starts_at <= a.requested_start
                    AND s.ends_at >= a.requested_start
                                       + make_interval(mins => service.duration_minutes)
              )
            """,
        )
        == 1
    )
    checks["accepted_transfer_has_supplemental_fact"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            JOIN business.appointment_events transfer
              ON transfer.appointment_id = a.id AND transfer.event_type = 'provider_reassigned'
            WHERE a.public_reference = 'APPT-TRANSFER'
              AND transfer.metadata @> '{"customer_accepted": true}'::jsonb
              AND EXISTS (
                  SELECT 1 FROM business.appointment_events completed
                  WHERE completed.appointment_id = a.id
                    AND completed.event_type = 'service_completed'
              )
            """,
        )
        == 1
    )

    expected_anomalies["missing_cancellation_event"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM business.appointments a
            WHERE a.public_reference = 'APPT-MISSING-EVENT'
              AND a.status = 'cancelled'
              AND NOT EXISTS (
                SELECT 1 FROM business.appointment_events e
                WHERE e.appointment_id = a.id AND e.event_type = 'appointment_cancelled'
              )
            """,
        )
        == 1
    )
    expected_anomalies["conflicting_cancellation_initiators"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT a.id
                FROM business.appointments a
                JOIN business.appointment_events e ON e.appointment_id = a.id
                WHERE a.public_reference = 'APPT-CONFLICT'
                  AND e.event_type = 'appointment_cancelled'
                GROUP BY a.id HAVING count(DISTINCT e.initiating_party) > 1
            ) conflict
            """,
        )
        == 1
    )
    expected_anomalies["duplicate_captured_payment"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT obligation_reference
                FROM business.payments
                WHERE captured_amount_cents > 0
                GROUP BY obligation_reference HAVING count(*) > 1
            ) duplicate_obligations
            """,
        )
        == 1
    )
    expected_anomalies["duplicate_membership_consumption"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*) FROM (
                SELECT related_appointment_id
                FROM business.membership_ledger
                WHERE entry_type = 'consume' AND related_appointment_id IS NOT NULL
                GROUP BY related_appointment_id HAVING count(*) > 1
            ) duplicates
            """,
        )
        == 1
    )
    expected_anomalies["provider_fee_was_captured"] = (
        await _scalar_int(
            session,
            """
            SELECT count(*)
            FROM business.appointments a
            JOIN business.invoice_items i ON i.appointment_id = a.id
            JOIN business.invoices inv ON inv.id = i.invoice_id
            JOIN business.payments p ON p.invoice_id = inv.id
            WHERE a.public_reference = 'APPT-CAN-PROVIDER'
              AND i.item_type = 'cancellation_fee' AND p.captured_amount_cents = 8000
            """,
        )
        == 1
    )

    row_counts, checksums = await _row_counts_and_checksums(session)
    return ValidationReport(checks, expected_anomalies, row_counts, checksums)


def dataset_fingerprint(checksums: dict[str, str]) -> str:
    canonical = json.dumps(checksums, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
