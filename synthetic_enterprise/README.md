# Synthetic Luma Enterprise

This directory is an independently generated stand-in for an existing company. It is not part of
the case-resolution product runtime.

- `business_spec/` defines the company, source-system contracts, policies, invariants, and reviewed
  decision tables before agent implementation.
- `luma_enterprise/` builds the deterministic operational and policy dataset.
- `data_generation/` contains public manifests and private incident truth used only for generation
  and evaluation.

The runtime under `src/luma/` must never import `luma_enterprise`. It accesses `business` and
`knowledge` as external read-only source schemas through operational and retrieval adapters. The
demo uses one PostgreSQL instance for convenience; production deployments can point those adapters
at separately owned services or databases.

Generate the enterprise before starting the product:

```powershell
uv run luma-generate-enterprise
```

Generation is destructive only to the synthetic `business` and `knowledge` schemas. It is never a
runtime startup step. The generator refuses to replace source data while application cases exist;
the force flag is reserved for isolated test/demo resets. No database foreign key crosses from
product-owned case history into the enterprise-owned schemas.
