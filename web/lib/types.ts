export type CaseRecord = {
  public_reference: string;
  source: string;
  claimed_customer_reference: string | null;
  contact_email: string | null;
  claimed_category: string | null;
  complaint_text: string;
  status: string;
  received_at: string;
  category?: string | null;
  outcome?: string | null;
  disposition?: string | null;
  escalation_reason?: string | null;
};

export type Overview = {
  total_cases: number;
  status_counts: Record<string, number>;
  active_cases: number;
  resolved_cases: number;
  pending_approval_cases: number;
  human_investigation_cases: number;
  resolution_rate: number | null;
  average_resolution_seconds: number | null;
};

export type PolicySearchResult = {
  section_id: string;
  policy_id: string;
  policy_title: string;
  policy_area: string;
  version: number;
  effective_from: string;
  effective_through: string | null;
  heading: string;
  body: string;
  lexical_rank: number | null;
  vector_rank: number | null;
  rrf_score: number;
};

export type OperationsResearchResult = {
  tool_name: string;
  evidence_type: string;
  metadata: {
    tool_call_id: string;
    tool_name: string;
    executed_at: string;
    source_system: string;
    truncated: boolean;
    result_count: number;
  };
  data: unknown;
};

export type ActionIntent = {
  public_reference: string;
  case_reference: string;
  action_type: string;
  target_type: string;
  target_reference: string;
  action_payload: Record<string, unknown>;
  status: string;
  created_at: string;
  approval?: { decision: string; rationale: string; decided_at: string; decided_by: string | null } | null;
  execution_attempts?: Array<Record<string, unknown>>;
};

export type CaseWorkspace = CaseRecord & {
  run: null | {
    run_number: number;
    architecture_version: string;
    model_provider: string | null;
    model_name: string | null;
    status: string;
    started_at: string | null;
    completed_at: string | null;
  };
  plan: Record<string, unknown> | null;
  stages: Array<{ stage_name: string; status: string; attempt_count: number; completed_at: string | null; error_code: string | null }>;
  evidence: Array<{ evidence_type: string; condition: string; source_reference: string | null; content: Record<string, unknown> }>;
  policy_retrievals: Array<{ query_text: string; effective_on: string; selected_section_ids: string[]; ranked_results: Array<Record<string, unknown>> }>;
  proposal: null | { outcome: string; disposition: string; rationale: string; action_payload: Record<string, unknown> | null; evidence_references: string[]; policy_references: string[] };
  verification: null | { supported: boolean; missing_evidence: string[]; contradictions: string[]; unsupported_claims: string[]; recommended_outcome: string; recommended_disposition: string; requires_human: boolean; rationale: string };
  actions: ActionIntent[];
  escalations: Array<{ reason_code: string; details: Record<string, unknown>; status: string; created_at: string; resolved_at?: string | null }>;
  final_communication: null | {
    communication_type: string;
    channel: string;
    recipient_email: string;
    subject: string;
    body: string;
    status: string;
    created_at: string;
    updated_at: string;
    sent_at: string | null;
    delivery_reference: string | null;
    sent_by: string | null;
  };
  events: Array<{ sequence: number; event_type: string; actor_type: string; actor_reference: string; occurred_at: string; payload: Record<string, unknown> }>;
};
