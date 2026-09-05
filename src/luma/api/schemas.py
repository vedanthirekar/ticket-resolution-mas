from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from luma.domain.cases import CaseSource, ClaimedCaseCategory


class CaseCreateRequest(BaseModel):
    complaint_text: str = Field(min_length=1, max_length=10_000)
    source: CaseSource = CaseSource.MANUAL
    external_request_key: str = Field(min_length=1, max_length=128)
    claimed_customer_reference: str | None = Field(default=None, max_length=32)
    claimed_category: ClaimedCaseCategory | None = None


class CaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    public_reference: str
    source: str
    claimed_customer_reference: str | None
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


class OperationsCaseWorkspaceResponse(CaseResponse):
    run: CaseRunResponse | None
    plan: dict[str, object] | None
    stages: list[WorkflowStageResponse]
    evidence: list[EvidenceResponse]
    policy_retrievals: list[PolicyRetrievalResponse]
    proposal: ProposalResponse | None
    verification: VerificationResponse | None
    actions: list[ActionDetailResponse]
    escalations: list[EscalationResponse]
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
