# Local Demo Runbook

## Prepare once

```powershell
Copy-Item .env.example .env
uv sync --dev
docker compose up -d postgres
uv run alembic upgrade head
uv run luma-generate-enterprise
uv run luma-index-policies
uv run luma-bootstrap
uv run luma-agent --setup-checkpoints
Set-Location web
npm install
Set-Location ..
```

Set `LUMA_MODEL_API_KEY` in `.env`. Never commit or paste that file into slides or
terminal recordings.

## Start the demo

Open four terminals from the repository root:

```powershell
uv run luma-api
```

```powershell
uv run luma-worker
```

```powershell
Set-Location web
npm run dev
```

```powershell
uv run luma-simulator --count 5
```

Use `http://localhost:3000/login` for operations and `/submit` for a manual customer
case. The simulator is optional and has no dashboard control.

## Five-minute interview path

1. Start on overview and point out product metrics only—no builder eval dashboard.
2. Submit the provider-cancelled complaint from `/submit`, or use
   `APPT-CAN-PROVIDER` with customer `CUS-0001`.
3. Watch the case move from queued to processing via SSE.
4. Open the case and walk through operational evidence, effective policy citation,
   proposed refund, independent verification, and persisted timeline.
5. Approve the frozen action with a rationale. Explain that the API writes a resume
   job atomically; the browser does not execute the refund.
6. Watch the worker resume the checkpoint, revalidate payment state, execute once,
   and mark the case resolved.
7. Show `docs/ARCHITECTURE.md`, an unsafe/conflicting case, and a generated eval
   report. State honestly that aggregate live metrics await a full Gate E run.

## Reliable fallback

If the model provider is unavailable, use the deterministic integration test below
to prove the same lifecycle without making a model-quality claim:

```powershell
$env:RUN_DB_TESTS = "1"
uv run pytest tests/integration/test_action_lifecycle.py -k worker_runs -vv
```

The deterministic model double exercises the real graph, PostgreSQL artifacts, job
queue, approval service, and action executor; only model generation is substituted.

## Deliberate reset and reseed

The generated business/policy dataset is deterministic, but cases and action side
effects are persistent. From the repository root, run the guarded reset script:

```powershell
.\scripts\reset-demo.ps1 -ConfirmDestructiveReset
```

The script verifies the repository marker, removes only this Compose project's
containers and volumes, recreates PostgreSQL, and reruns migrations, generation,
policy indexing, bootstrap, and checkpoint setup. It destroys the local demo
database, so the explicit confirmation switch is required.
