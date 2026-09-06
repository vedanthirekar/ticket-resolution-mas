from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from luma.agents.contracts import OperationalToolName
from luma.domain.cases import CaseSource, ClaimedCaseCategory


class CaseCreateRequest(BaseModel):
    complaint_text: str = Field(min_length=1, max_length=10_000)
    source: CaseSource = CaseSource.MANUAL
    external_request_key: str = Field(min_length=1, max_length=128)
    claimed_customer_reference: str | None = Field(default=None, max_length=32)
    contact_email: str | None = Field(default=None, max_length=320)
    claimed_category: ClaimedCaseCategory | None = None

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if "@" not in normalized or "." not in normalized.rsplit("@", 1)[-1]:
            raise ValueError("contact_email must be a valid email address")
        return normalized


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_reference: str
    source: str
    claimed_customer_reference: str | None
    contact_email: str | None
    claimed_category: str | None
    complaint_text: str
    status: str
    received_at: datetime
    created: bool | None = None


class CaseEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sequence: int
    event_type: str
    actor_type: str
    actor_reference: str
    occurred_at: datetime
    payload: dict[str, object]


class CaseDetailResponse(CaseResponse):
    events: list[CaseEventResponse]


class OperationsOverviewResponse(BaseModel):
    total_cases: int
    status_counts: dict[str, int]
    active_cases: int
    resolved_cases: int
    pending_approval_cases: int
    human_investigation_cases: int
    resolution_rate: float | None
    average_resolution_seconds: float | None


class OperationsCaseResponse(CaseResponse):
    category: str | None = None
    outcome: str | None = None
    disposition: str | None = None
    escalation_reason: str | None = None


class CaseRunResponse(BaseModel):
    run_number: int
    architecture_version: str
    model_provider: str | None
    model_name: str | None
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    input_tokens: int | None
    output_tokens: int | None
    estimated_cost_usd: float | None
    error_code: str | None


class WorkflowStageResponse(BaseModel):
    stage_name: str
    status: str
    attempt_count: int
    completed_at: datetime | None
    error_code: str | None


class EvidenceResponse(BaseModel):
    evidence_type: str
    condition: str
    source_system: str
    source_reference: str | None
    observed_as_of: datetime
    content: dict[str, object]


class PolicyRetrievalResponse(BaseModel):
    query_text: str
    effective_on: date
    selected_section_ids: list[str]
    ranked_results: list[dict[str, object]]


class PolicySearchResultResponse(BaseModel):
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


class OperationsResearchRequest(BaseModel):
    tool_name: OperationalToolName
    arguments: dict[str, Any]


class OperationsResearchResponse(BaseModel):
    tool_name: OperationalToolName
    evidence_type: str
    metadata: dict[str, Any]
    data: Any


class InvestigationNoteRequest(BaseModel):
    note: str = Field(min_length=1, max_length=4000)


class InvestigationResolutionRequest(BaseModel):
    resolution_code: Literal[
        "no_action_required",
        "customer_guidance_provided",
        "corrected_externally",
        "other_manual_resolution",
    ]
    resolution_summary: str = Field(min_length=3, max_length=2000)
    customer_response: str = Field(min_length=3, max_length=4000)


class InvestigationUpdateResponse(BaseModel):
    case_status: str
    escalation_status: str


class CustomerEmailDraftRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=240)
    body: str = Field(min_length=1, max_length=10_000)


class CustomerCommunicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    communication_type: str
    channel: str
    recipient_email: str
    subject: str
    body: str
    status: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    delivery_reference: str | None
    sent_by: str | None = None


class ProposalResponse(BaseModel):
    outcome: str
    disposition: str
    rationale: str
    action_payload: dict[str, object] | None
    evidence_references: list[str]
    policy_references: list[str]


class VerificationResponse(BaseModel):
    supported: bool
    missing_evidence: list[str]
    contradictions: list[str]
    unsupported_claims: list[str]
    recommended_outcome: str
    recommended_disposition: str
    requires_human: bool
    rationale: str


class ApprovalDetailResponse(BaseModel):
    decision: str
    rationale: str
    decided_at: datetime
    decided_by: str | None


class ExecutionAttemptResponse(BaseModel):
    action_intent_reference: str
    attempt_number: int
    executor: str
    status: str
    external_reference: str | None
    response_payload: dict[str, object]
    error_code: str | None
    error_detail: str | None
    started_at: datetime
    completed_at: datetime | None


class ActionDetailResponse(BaseModel):
    public_reference: str
    action_type: str
    target_type: str
    target_reference: str
    action_payload: dict[str, object]
    status: str
    created_at: datetime
    approval: ApprovalDetailResponse | None
    execution_attempts: list[ExecutionAttemptResponse]


class EscalationResponse(BaseModel):
    reason_code: str
    details: dict[str, object]
    status: str
    created_at: datetime
    resolved_at: datetime | None


class RecommendationPresentationResponse(BaseModel):
    headline: str
    explanation: str
    key_facts: list[str]
    next_step: str
    technical_rationale: str


class OperationsCaseWorkspaceResponse(CaseResponse):
    run: CaseRunResponse | None
    plan: dict[str, object] | None
    stages: list[WorkflowStageResponse]
    evidence: list[EvidenceResponse]
    policy_retrievals: list[PolicyRetrievalResponse]
    proposal: ProposalResponse | None
    verification: VerificationResponse | None
    recommendation: RecommendationPresentationResponse | None
    actions: list[ActionDetailResponse]
    escalations: list[EscalationResponse]
    final_communication: CustomerCommunicationResponse | None
    events: list[CaseEventResponse]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=1, max_length=256)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class AccountResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    display_name: str


class ActionIntentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_reference: str
    case_reference: str
    action_type: str
    target_type: str
    target_reference: str
    action_payload: dict[str, object]
    status: str
    created_at: datetime


class ActionDecisionRequest(BaseModel):
    decision: Literal["approved", "rejected"]
    rationale: str = Field(min_length=1, max_length=2000)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    decision: str
    rationale: str
    decided_at: datetime
