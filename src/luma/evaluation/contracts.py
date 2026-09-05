from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExpectedAction(StrictModel):
    action_type: str
    target_reference: str
    amount_cents: int | None = None
    credit_delta: int | None = None


class EvalCase(StrictModel):
    case_id: str
    scenario_id: str
    split: Literal["development", "held_out"]
    test_type: Literal["happy_path", "boundary", "counterfactual", "adversarial", "tool_failure"]
    complaint: str
    customer_reference: str | None
    expected_category: str
    expected_outcome: str | None
    expected_disposition: Literal["auto_resolve", "human_approval", "human_investigation"]
    required_evidence_types: list[str]
    required_source_references: list[str]
    required_policy_references: list[str]
    expected_tools: list[str]
    expected_action: ExpectedAction | None = None
    forbidden_actions: list[str] = Field(default_factory=list)
    expected_escalation_reasons: list[str] = Field(default_factory=list)
    fault_injection: dict[str, Any] | None = None

    @model_validator(mode="after")
    def approval_requires_action(self) -> EvalCase:
        if self.expected_disposition == "human_approval" and self.expected_action is None:
            raise ValueError("human_approval cases require expected_action")
        return self


class EvalDataset(StrictModel):
    dataset_name: str
    dataset_version: str
    business_dataset_version: str
    business_dataset_fingerprint: str
    created_at: datetime
    cases: list[EvalCase]


class EvalObservation(StrictModel):
    case_id: str
    case_reference: str | None = None
    case_run_id: str | None = None
    category: str | None = None
    outcome: str | None = None
    disposition: str | None = None
    evidence_types: list[str] = Field(default_factory=list)
    source_references: list[str] = Field(default_factory=list)
    policy_references: list[str] = Field(default_factory=list)
    tools_called: list[str] = Field(default_factory=list)
    action: dict[str, Any] | None = None
    escalation_reason: str | None = None
    verifier_supported: bool | None = None
    unauthorized_mutation_count: int = 0
    duplicate_execution_count: int = 0
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    error: str | None = None


class MetricResult(StrictModel):
    name: str
    score: float | None
    passed: bool | None
    details: dict[str, Any] = Field(default_factory=dict)


class CaseGrade(StrictModel):
    case_id: str
    scenario_id: str
    split: str
    test_type: str
    passed: bool
    metrics: list[MetricResult]


class EvalReport(StrictModel):
    experiment_id: str
    created_at: datetime
    dataset_name: str
    dataset_version: str
    business_dataset_version: str
    architecture_version: str
    prompt_version: str
    tool_version: str
    graph_version: str
    model_provider: str
    model_name: str
    configuration: dict[str, Any]
    summary: dict[str, Any]
    observations: list[EvalObservation]
    cases: list[CaseGrade]
