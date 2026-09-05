# M10 Evaluation Report and Error Analysis

Status: implementation evidence complete; Gate E model-quality validation pending

## Evidence reviewed

The evaluation runner produced seven one-case development smoke reports on
September 4, 2026. These are real runner outputs, not UI constants. The selected
successful baseline is experiment `EXP-20260904T160608-6ffdbfb8` using
`gemini-3.5-flash`, `luma_cases_v1`, `luma_business_v1`, `multi-agent-v1`,
`prompts-v1`, and `langgraph-v1`.

That run passed its one happy-path cancellation-fee case and all applicable
deterministic graders: classification, decision, disposition, evidence, source,
policy and tool recall, exact action, and action safety. It recorded no unauthorized
or duplicate action, a verifier false-rejection rate of zero for the single reviewed
case, 65.6 seconds latency, 12,337 input tokens, and 4,113 output tokens.

This is smoke evidence only. A sample of one is not an aggregate quality result,
does not satisfy Gate E, and predates the current `prompts-v2`/`langgraph-v2`
configuration.

## Error analysis

The six unsuccessful smoke attempts exposed four distinct failure classes:

| Failure class | Observed symptom | Disposition |
|---|---|---|
| Provider availability | Gemini 3.8 returned HTTP 503; a later OpenRouter run ended in a connection error | Keep retries bounded and use the deterministic demo fallback; do not present these as model-quality failures |
| Structured-output reliability | Gemini 3.7 failed case-manager plan validation; Gemini 3.5 later failed verifier-output validation | Preserve typed boundaries and stage retries; measure again after routing/prompt work resumes |
| Proposal/pre-verification mismatch | One Gemini 3.5 run found the right evidence and policy but produced an unsupported decision that deterministically escalated | The fail-closed control worked; the action schema and deterministic proposal boundaries were subsequently tightened |
| End-to-end behavioral miss | Another completed Gemini 3.7 attempt failed the single case without a provider exception | Retain as model/architecture error; investigate only when routing, prompts, and handoffs return to scope |

The newest attempted OpenRouter report used `z-ai/glm-5.2:free` and failed before a
usable model response because of connectivity. It supplies no evidence about the
current default model's decision quality.

## Release interpretation

- Offline dataset validation, retrieval evaluation, deterministic graders, and
  safety/integration tests belong in CI and must pass for every change.
- The successful smoke proves that the full path can work; it does not establish a
  pass rate.
- Gate E remains open until the current frozen configuration completes the full
  development split, any changes are justified and frozen, and the untouched
  held-out split meets the thresholds in
  `docs/decisions/M8_EVALUATION_AND_OBSERVABILITY.md`.
- Routing, prompts, node architecture, and handoff optimization are explicitly held
  for the next quality iteration. M10 does not conceal that limitation.
