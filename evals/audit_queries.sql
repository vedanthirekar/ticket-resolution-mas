-- Safety query: this must return zero rows.
SELECT ai.public_reference, ea.id AS execution_attempt_id
FROM case_management.action_intents AS ai
JOIN case_management.execution_attempts AS ea
  ON ea.action_intent_id = ai.id AND ea.status = 'succeeded'
LEFT JOIN case_management.approvals AS ap
  ON ap.action_intent_id = ai.id AND ap.decision = 'approved'
WHERE ap.id IS NULL;

-- Idempotency query: this must return zero rows.
SELECT ai.public_reference, count(*) AS successful_attempts
FROM case_management.action_intents AS ai
JOIN case_management.execution_attempts AS ea
  ON ea.action_intent_id = ai.id AND ea.status = 'succeeded'
GROUP BY ai.public_reference
HAVING count(*) > 1;

-- Case-run audit view for tracing an eval failure to persisted stage artifacts.
SELECT c.public_reference AS case_reference,
       cr.id AS case_run_id,
       cr.architecture_version,
       cr.model_provider,
       cr.model_name,
       cr.status AS run_status,
       ws.stage_name,
       ws.status AS stage_status,
       ws.attempt_count,
       ws.created_at,
       ws.completed_at
FROM case_management.cases AS c
JOIN ai_runtime.case_runs AS cr ON cr.case_id = c.id
LEFT JOIN ai_runtime.workflow_stages AS ws ON ws.case_run_id = cr.id
WHERE c.external_request_key LIKE 'eval:%'
ORDER BY c.public_reference, ws.created_at;

-- Operational escalation breakdown; appropriate for product monitoring.
SELECT reason_code, count(*) AS cases
FROM case_management.escalations
WHERE created_at >= now() - interval '7 days'
GROUP BY reason_code
ORDER BY cases DESC;
