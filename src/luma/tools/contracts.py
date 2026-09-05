from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ToolMetadata(StrictModel):
    tool_call_id: str
    tool_name: str
    executed_at: datetime
    source_system: str = "luma_postgresql"
    truncated: bool = False
    result_count: int = 0


class Provenance(StrictModel):
    source_table: str
    source_reference: str


class ToolResult[T](StrictModel):
    metadata: ToolMetadata
    data: T


class CustomerRefInput(StrictModel):
    customer_reference: str = Field(min_length=1, max_length=24)


class CustomerAppointmentsInput(CustomerRefInput):
    starts_on_or_after: datetime | None = None
    starts_before: datetime | None = None
    limit: int = Field(default=20, ge=1, le=50)


class AppointmentEvidenceInput(CustomerRefInput):
    appointment_reference: str = Field(min_length=1, max_length=32)


class MembershipEvidenceInput(CustomerRefInput):
    membership_reference: str | None = Field(default=None, max_length=32)
    as_of: datetime
    limit: int = Field(default=100, ge=1, le=200)


class BookingAttemptEvidenceInput(CustomerRefInput):
    booking_attempt_reference: str = Field(min_length=1, max_length=32)


class CustomerBookingAttemptsInput(CustomerRefInput):
    starts_on_or_after: datetime | None = None
    starts_before: datetime | None = None
    limit: int = Field(default=20, ge=1, le=50)


class CustomerEvidence(StrictModel):
    customer_reference: str
    display_name: str
    masked_email: str | None
    masked_phone: str | None
    email_verified: bool
    phone_verified: bool
    active: bool
    provenance: Provenance


class AppointmentSummary(StrictModel):
    appointment_reference: str
    customer_reference: str
    location_reference: str
    service_reference: str
    service_name: str
    employee_reference: str
    scheduled_start: datetime
    scheduled_end: datetime
    status: str
    quoted_price_cents: int
    quoted_credit_cost: int | None
    currency: str
    booking_channel: str
    predecessor_appointment_reference: str | None
    provenance: Provenance


class AppointmentEventEvidence(StrictModel):
    event_reference: str
    event_type: str
    actor_type: str
    actor_reference: str
    initiating_party: str
    reason_code: str | None
    occurred_at: datetime
    recorded_at: datetime
    channel: str
    correlation_reference: str | None
    event_metadata: dict[str, object]
    provenance: Provenance


class AppointmentTimeline(StrictModel):
    appointment: AppointmentSummary
    events: list[AppointmentEventEvidence]
    successor_appointments: list[AppointmentSummary] = Field(default_factory=list)


class InvoiceItemEvidence(StrictModel):
    item_reference: str
    item_type: str
    description: str
    quantity: int
    amount_cents: int
    currency: str
    provenance: Provenance


class PaymentEventEvidence(StrictModel):
    event_reference: str
    event_type: str
    amount_cents: int
    occurred_at: datetime
    processor_event_reference: str | None
    provenance: Provenance


class RefundEvidence(StrictModel):
    refund_reference: str
    amount_cents: int
    status: str
    reason_code: str
    completed_at: datetime | None
    provenance: Provenance


class PaymentEvidence(StrictModel):
    payment_reference: str
    invoice_reference: str
    obligation_reference: str
    status: str
    tender_type: str
    amount_cents: int
    authorized_amount_cents: int
    captured_amount_cents: int
    refunded_amount_cents: int
    refundable_amount_cents: int
    currency: str
    created_at: datetime
    items: list[InvoiceItemEvidence]
    events: list[PaymentEventEvidence]
    refunds: list[RefundEvidence]
    provenance: Provenance


class AppointmentPayments(StrictModel):
    appointment_reference: str
    payments: list[PaymentEvidence]


class LedgerAllocationEvidence(StrictModel):
    grant_entry_reference: str
    quantity: int
    provenance: Provenance


class MembershipLedgerEvidence(StrictModel):
    ledger_reference: str
    entry_type: str
    credit_delta: int
    effective_at: datetime
    expires_at: datetime | None
    related_appointment_reference: str | None
    related_entry_reference: str | None
    reason_code: str
    approval_reference: str | None
    allocations: list[LedgerAllocationEvidence]
    provenance: Provenance


class MembershipEvidence(StrictModel):
    membership_reference: str
    customer_reference: str
    plan_reference: str
    plan_name: str
    status: str
    starts_at: date
    ends_at: date | None
    terms_policy_id: str
    terms_version: int
    derived_balance: int
    ledger: list[MembershipLedgerEvidence]
    provenance: Provenance


class ConfigurationFact(StrictModel):
    fact_type: str
    condition: Literal["present", "known_absent"] = "present"
    value: dict[str, object]
    provenance: Provenance


class BookingAttemptEvidence(StrictModel):
    booking_attempt_reference: str
    customer_reference: str
    location_reference: str
    service_reference: str
    requested_employee_reference: str | None
    requested_start: datetime
    status: str
    reason_code: str | None
    committed_appointment_reference: str | None
    configuration_facts: list[ConfigurationFact]
    provenance: Provenance


class BookingAttemptSummary(StrictModel):
    booking_attempt_reference: str
    customer_reference: str
    location_reference: str
    service_reference: str
    requested_employee_reference: str | None
    requested_start: datetime
    status: str
    reason_code: str | None
    committed_appointment_reference: str | None
    provenance: Provenance


class PolicySearchInput(StrictModel):
    query: str = Field(min_length=2, max_length=500)
    effective_on: date
    policy_id: str | None = Field(default=None, max_length=32)
    policy_area: str | None = Field(default=None, max_length=64)
    location_reference: str | None = Field(default=None, max_length=24)
    service_reference: str | None = Field(default=None, max_length=24)
    limit: int = Field(default=5, ge=1, le=10)


class PolicySearchHit(StrictModel):
    section_id: str
    policy_id: str
    policy_title: str
    policy_area: str
    version: int
    effective_from: date
    effective_through: date | None
    heading: str
    body: str
    lexical_rank: int | None
    vector_rank: int | None
    rrf_score: float
    provenance: Provenance


class PolicySectionFetchInput(StrictModel):
    section_id: str = Field(min_length=1, max_length=96)
    effective_on: date
    location_reference: str | None = Field(default=None, max_length=24)
    service_reference: str | None = Field(default=None, max_length=24)


class PolicySectionDetail(StrictModel):
    section: PolicySearchHit
    parent: PolicySearchHit | None
    linked_sections: list[PolicySearchHit]
    link_types: dict[str, Literal["references", "exception_to", "supersedes", "related"]]
