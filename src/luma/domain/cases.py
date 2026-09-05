from __future__ import annotations

from enum import StrEnum


class CaseStatus(StrEnum):
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    PENDING_APPROVAL = "pending_approval"
    RESOLVED = "resolved"
    HUMAN_INVESTIGATION = "human_investigation"
    FAILED = "failed"


class CaseSource(StrEnum):
    MANUAL = "manual"
    SIMULATOR = "simulator"
    API = "api"


class ClaimedCaseCategory(StrEnum):
    """Customer-selected routing hint; never treated as authoritative evidence."""

    DUPLICATE_PAYMENT = "duplicate_payment"
    CANCELLATION_FEE_DISPUTE = "cancellation_fee_dispute"
    MISSING_APPOINTMENT = "missing_appointment"
    MEMBERSHIP_CREDITS = "membership_credits"
    ONLINE_BOOKING_UNAVAILABLE = "online_booking_unavailable"
    OTHER = "other"


class JobStatus(StrEnum):
    QUEUED = "queued"
    LEASED = "leased"
    RETRY_WAIT = "retry_wait"
    SUCCEEDED = "succeeded"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class FailureKind(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"


TERMINAL_CASE_STATUSES = frozenset(
    {CaseStatus.RESOLVED, CaseStatus.HUMAN_INVESTIGATION, CaseStatus.FAILED}
)

ALLOWED_CASE_TRANSITIONS: dict[CaseStatus, frozenset[CaseStatus]] = {
    CaseStatus.RECEIVED: frozenset({CaseStatus.QUEUED, CaseStatus.HUMAN_INVESTIGATION}),
    CaseStatus.QUEUED: frozenset(
        {CaseStatus.PROCESSING, CaseStatus.HUMAN_INVESTIGATION, CaseStatus.FAILED}
    ),
    CaseStatus.PROCESSING: frozenset(
        {
            CaseStatus.PENDING_APPROVAL,
            CaseStatus.RESOLVED,
            CaseStatus.HUMAN_INVESTIGATION,
            CaseStatus.FAILED,
        }
    ),
    CaseStatus.PENDING_APPROVAL: frozenset(
        {CaseStatus.RESOLVED, CaseStatus.HUMAN_INVESTIGATION, CaseStatus.FAILED}
    ),
    CaseStatus.RESOLVED: frozenset(),
    CaseStatus.HUMAN_INVESTIGATION: frozenset(),
    CaseStatus.FAILED: frozenset(),
}
