# Luma Business Dataset Generation

This build-only subsystem creates `luma_business_v1` from an empty migrated
PostgreSQL database. It is deterministic and is excluded from the production
runtime wheel.

## Frozen configuration

- Dataset: `luma_business_v1`
- Generator: `1.0.0`
- Seed: `20260903`
- Reference time: `2026-09-01T12:00:00Z`
- Schema revision: `20260905_0011`

## Build pipeline

```text
approved company/catalog
  -> customers and memberships
  -> concrete provider schedules and booking configuration
  -> ordinary appointment lifecycles
  -> invoices, payment attempts, refunds, and membership ledger effects
  -> declared canonical operational incidents
  -> versioned policy parsing and section indexing
  -> independent integrity/reconciliation checks
  -> logical table checksums and frozen manifest
```

The generator replaces all `business` and `knowledge` rows in one transaction.
Validation runs after the committed replacement; a failed validation prevents a
manifest from being published and reports the exact failed check.

## Commands

With PostgreSQL running and migrations applied:

```powershell
uv run luma-generate-enterprise
```

Validate without writing manifest files:

```powershell
uv run luma-generate-enterprise --no-write-manifests
```

Run the full reproducibility test, which rebuilds twice and compares all logical
checksums:

```powershell
$env:RUN_DB_TESTS = "1"
uv run pytest tests/data_integrity/test_generated_dataset.py
```

## Manifest boundaries

- `manifests/luma_business_v1.json` is the public freeze record: configuration,
  counts, canonical references, validation summary, checksums, and fingerprint.
- `private_manifests/luma_business_v1_incidents.json` is build/evaluation truth. It
  declares intentionally designed incidents and expected anomalies.
- Neither directory is part of the application package. The generator module is
  also excluded from the runtime wheel. Runtime services query only PostgreSQL
  operational and knowledge schemas and never read incident labels.

Logical checksums include deterministic UUIDv5 keys and business values. Generic
`created_at`, `updated_at`, and `recorded_at` columns are excluded from the checksum
contract; material event/effective times remain included.

## Versioning rule

Changing approved business meaning, schema, generator behavior, seed, or canonical
incident construction requires either an explicit rebuild and new fingerprint or a
new dataset contract such as `luma_business_v2`. Evaluation results must always
record both dataset version and fingerprint.
