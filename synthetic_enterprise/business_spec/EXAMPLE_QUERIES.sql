-- Appointment history: proves transition authorship and initiating party separately.
SELECT
    a.public_reference AS appointment_reference,
    ae.public_reference AS event_reference,
    ae.event_type,
    ae.actor_type,
    ae.actor_reference,
    ae.initiating_party,
    ae.reason_code,
    ae.occurred_at
FROM business.appointments AS a
JOIN business.appointment_events AS ae ON ae.appointment_id = a.id
WHERE a.public_reference = :appointment_reference
ORDER BY ae.occurred_at, ae.id;

-- Duplicate-capture candidates: shared obligation is the primary join key.
SELECT
    p.obligation_reference,
    array_agg(p.public_reference ORDER BY p.created_at) AS payment_references,
    count(*) AS captures,
    sum(p.captured_amount_cents) AS total_captured_cents
FROM business.payments AS p
WHERE p.customer_id = :customer_id
  AND p.status IN ('captured', 'partially_refunded', 'refunded')
GROUP BY p.obligation_reference
HAVING count(*) > 1;

-- Refundable amount from authoritative successful refunds.
SELECT
    p.public_reference,
    p.captured_amount_cents
        - coalesce(sum(r.amount_cents) FILTER (WHERE r.status = 'succeeded'), 0)
        AS refundable_amount_cents
FROM business.payments AS p
LEFT JOIN business.refunds AS r ON r.payment_id = p.id
WHERE p.public_reference = :payment_reference
GROUP BY p.id;

-- Membership balance at an instant; no mutable balance column is required.
SELECT coalesce(sum(ml.credit_delta), 0) AS available_credits
FROM business.membership_ledger AS ml
JOIN business.memberships AS m ON m.id = ml.membership_id
WHERE m.public_reference = :membership_reference
  AND ml.effective_at <= :as_of;

-- Policy sections effective on a business-local calendar date with lexical rank.
SELECT
    pd.policy_id,
    pv.version,
    ps.section_id,
    ps.heading,
    ts_rank(ps.search_vector, websearch_to_tsquery('english', :query)) AS lexical_rank
FROM knowledge.policy_sections AS ps
JOIN knowledge.policy_versions AS pv ON pv.id = ps.policy_version_id
JOIN knowledge.policy_documents AS pd ON pd.id = pv.policy_document_id
WHERE pv.effective_from <= :event_local_date
  AND (pv.effective_through IS NULL OR pv.effective_through >= :event_local_date)
  AND ps.search_vector @@ websearch_to_tsquery('english', :query)
ORDER BY lexical_rank DESC, ps.section_id
LIMIT :limit;

