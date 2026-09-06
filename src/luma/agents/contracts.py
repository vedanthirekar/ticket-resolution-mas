from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CaseCategory(StrEnum):
    DUPLICATE_PAYMENT = "duplicate_payment"
    CANCELLATION_FEE_DISPUTE = "cancellation_fee_dispute"
    MISSING_APPOINTMENT = "missing_appointment"
    MEMBERSHIP_CREDITS = "membership_credits"
    ONLINE_BOOKING_UNAVAILABLE = "online_booking_unavailable"
    UNKNOWN = "unknown"


OperationalToolName = Literal[
    "get_customer",
    "get_customer_appointments",
    "get_appointment_timeline",
    "get_appointment_payments",
    "get_membership_evidence",
    "get_customer_booking_attempts",
    "get_booking_attempt_evidence",
]


class CustomerScopedArguments(StrictModel):
    """Model-supplied arguments whose customer scope is verified and injected by the app."""

    customer_reference: str | None = Field(default=None, min_length=1, max_length=24)


class CustomerDiscoveryArguments(CustomerScopedArguments):
    starts_on_or_after: datetime | None = None
    starts_before: datetime | None = None
    limit: int | None = Field(default=None, ge=1, le=50)


class AppointmentReferenceArguments(CustomerScopedArguments):
    appointment_reference: str = Field(min_length=1, max_length=32)


class MembershipEvidenceArguments(CustomerScopedArguments):
    membership_reference: str | None = Field(default=None, max_length=32)
    as_of: datetime
    limit: int | None = Field(default=None, ge=1, le=200)


class BookingAttemptReferenceArguments(CustomerScopedArguments):
    booking_attempt_reference: str = Field(min_length=1, max_length=32)


class OperationalCallBase(StrictModel):
    purpose: str = Field(min_length=3, max_length=300)


class GetCustomerCall(OperationalCallBase):
    tool_name: Literal["get_customer"]
    arguments: CustomerScopedArguments


class GetCustomerAppointmentsCall(OperationalCallBase):
    tool_name: Literal["get_customer_appointments"]
    arguments: CustomerDiscoveryArguments


class GetAppointmentTimelineCall(OperationalCallBase):
    tool_name: Literal["get_appointment_timeline"]
    arguments: AppointmentReferenceArguments


class GetAppointmentPaymentsCall(OperationalCallBase):
    tool_name: Literal["get_appointment_payments"]
    arguments: AppointmentReferenceArguments


class GetMembershipEvidenceCall(OperationalCallBase):
    tool_name: Literal["get_membership_evidence"]
    arguments: MembershipEvidenceArguments


class GetCustomerBookingAttemptsCall(OperationalCallBase):
    tool_name: Literal["get_customer_booking_attempts"]
    arguments: CustomerDiscoveryArguments


class GetBookingAttemptEvidenceCall(OperationalCallBase):
    tool_name: Literal["get_booking_attempt_evidence"]
    arguments: BookingAttemptReferenceArguments


OperationalCall = Annotated[
    GetCustomerCall
    | GetCustomerAppointmentsCall
    | GetAppointmentTimelineCall
    | GetAppointmentPaymentsCall
    | GetMembershipEvidenceCall
    | GetCustomerBookingAttemptsCall
    | GetBookingAttemptEvidenceCall,
    Field(discriminator="tool_name"),
]


class InvestigationPlanOutput(StrictModel):
    category: CaseCategory
    material_event_date: date
    required_evidence_types: list[str] = Field(max_length=10)
    investigation_objectives: list[str] = Field(min_length=1, max_length=10)
    policy_query: str = Field(min_length=2, max_length=500)
    policy_area: str | None = Field(default=None, max_length=64)
    rationale: str = Field(min_length=3, max_length=1000)


class InvestigationDecisionOutput(StrictModel):
    complete: bool
    next_call: OperationalCall | None = None
    rationale: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def call_matches_completion(self) -> InvestigationDecisionOutput:
        if self.complete and self.next_call is not None:
            raise ValueError("a complete investigation cannot request another call")
        if not self.complete and self.next_call is None:
            raise ValueError("an incomplete investigation must request a call")
        return self


class EvidenceRecord(StrictModel):
    evidence_type: str
    condition: Literal[
        "present",
        "known_absent",
        "missing",
        "unknown",
        "contradictory",
        "unavailable",
        "not_applicable",
    ]
    tool_name: str
    tool_call_id: str | None = None
    source_references: list[str] = Field(default_factory=list)
    content: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EvidenceCoverageOutput(StrictModel):
    complete: bool
    missing_evidence: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    unavailable_evidence: list[str] = Field(default_factory=list)


class PolicyAssessmentOutput(StrictModel):
    applicable: bool
    selected_section_ids: list[str] = Field(max_length=5)
    rule_summary: str = Field(min_length=3, max_length=1500)
    missing_evidence_types: list[str] = Field(default_factory=list, max_length=5)
    supplemental_call: OperationalCall | None = None

    @model_validator(mode="after")
    def supplemental_call_matches_missing_evidence(self) -> PolicyAssessmentOutput:
        if self.supplemental_call is not None and not self.missing_evidence_types:
            # A weak model can emit an unnecessary call while also declaring that no
            # evidence is missing. Fail safely by discarding the call, never by executing
            # an operational lookup without a stated evidence need.
            self.supplemental_call = None
        return self


class RefundPaymentAction(StrictModel):
    action_type: Literal["refund_payment"]
    payment_reference: str = Field(min_length=1, max_length=32)
    amount_cents: int = Field(gt=0)
    reason_code: str = Field(min_length=2, max_length=64)


class AdjustMembershipCreditAction(StrictModel):
    action_type: Literal["adjust_membership_credit"]
    membership_reference: str = Field(min_length=1, max_length=32)
    credit_delta: int
    reason_code: str = Field(min_length=2, max_length=64)

    @model_validator(mode="after")
    def nonzero_delta(self) -> AdjustMembershipCreditAction:
        if self.credit_delta == 0:
            raise ValueError("credit_delta must be nonzero")
        return self


ResolutionOutcome = Literal[
    "refund_cancellation_fee",
    "retain_cancellation_fee",
    "retain_no_show_fee",
    "refund_duplicate_payment",
    "explain_distinct_charges",
    "explain_authorization_hold",
    "restore_duplicate_credit",
    "explain_booking_restriction",
    "escalate_booking_technical_failure",
    "insufficient_grounding",
]
ActionPayload = Annotated[
    RefundPaymentAction | AdjustMembershipCreditAction,
    Field(discriminator="action_type"),
]


class ResolutionProposalOutput(StrictModel):
    outcome: ResolutionOutcome
    disposition: Literal["auto_resolve", "human_approval", "human_investigation"]
    rationale: str = Field(min_length=3, max_length=2000)
    action_payload: ActionPayload | None = None
    evidence_references: list[str]
    policy_references: list[str]

    @model_validator(mode="after")
    def mutations_require_approval(self) -> ResolutionProposalOutput:
        if self.action_payload and self.disposition != "human_approval":
            raise ValueError("all proposed mutations require human approval")
        return self


class VerificationOutput(StrictModel):
    """Independent semantic review; deterministic code owns the final disposition."""

    supported: bool
    missing_evidence: list[str] = Field(default_factory=list, max_length=10)
    contradictions: list[str] = Field(default_factory=list, max_length=10)
    unsupported_claims: list[str] = Field(default_factory=list, max_length=10)
    recommended_outcome: ResolutionOutcome
    recommended_disposition: Literal["auto_resolve", "human_approval", "human_investigation"]
    requires_human: bool
    rationale: str = Field(min_length=3, max_length=2000)


class CaseResolutionState(TypedDict, total=False):
    case_id: str
    case_reference: str
    case_run_id: str
    case_received_at: str
    complaint_text: str
    customer_reference: str | None
    claimed_category: str | None
    plan: dict[str, Any]
    evidence: list[dict[str, Any]]
    evidence_coverage: dict[str, Any]
    policy_results: list[dict[str, Any]]
    policy_assessment: dict[str, Any]
    supplemental_count: int
    proposal: dict[str, Any]
    preverification: dict[str, Any]
    verification: dict[str, Any]
    final_disposition: Literal["auto_resolve", "human_approval", "human_investigation"]
    action_intent_reference: str
    approval_decision: Literal["approved", "rejected"]
    execution_receipt: dict[str, Any]
    customer_response: str
    escalation_reason: str | None
    input_tokens: int
    output_tokens: int


CATEGORY_REQUIRED_EVIDENCE: dict[CaseCategory, frozenset[str]] = {
    CaseCategory.DUPLICATE_PAYMENT: frozenset(
        {"customer_identity", "appointment_timeline", "payment"}
    ),
    CaseCategory.CANCELLATION_FEE_DISPUTE: frozenset(
        {"customer_identity", "appointment_timeline", "payment"}
    ),
    CaseCategory.MISSING_APPOINTMENT: frozenset({"customer_identity", "booking_history"}),
    CaseCategory.MEMBERSHIP_CREDITS: frozenset({"customer_identity", "membership_ledger"}),
    CaseCategory.ONLINE_BOOKING_UNAVAILABLE: frozenset(
        {"customer_identity", "booking_configuration"}
    ),
    CaseCategory.UNKNOWN: frozenset(),
}
