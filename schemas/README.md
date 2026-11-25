# Policy JSON Schema

This directory holds the generated, versioned JSON Schema that describes the
`perfcheck` collection policy. It is the machine-readable contract that authors
and editors use to author and validate a policy file.

## What this is and is not

The schema is a **hosted, versioned public contract**. It is generated from the
`SuitePolicy` pydantic types and committed here; it is not a promise of Python
API or artifact-schema stability. Internal implementation may change during
cleanup. See the [root scope statement](../README.md#scope).

## Hosted pointer convention

The schema is pinned to a single major version and served raw from the default
branch so editors can fetch it to validate a policy as it is authored:

- Committed path: `schemas/v1/perfcheck-policy.schema.json`
- `$id` and the value a policy's `$schema` points at:
  `https://raw.githubusercontent.com/geoder101/perfcheck/refs/heads/main/schemas/v1/perfcheck-policy.schema.json`
  (JSON Schema draft 2020-12)

Editors and AI tooling resolve this single public URL. It pins the exact major
version; it does not track patch or minor changes.

## Versioning and immutability

Versioning is major-only, keyed to the policy's `schema_version` field:

- Additive changes go to a new version path (`schemas/v2/...`).
- Breaking changes go to a new major path (`schemas/v2/...`).
- Committed versioned files are never overwritten in place. `just schema-check`
  enforces this by regenerating from source and requiring byte-identical output.

Regenerate the schema from source with `uv run python -m tools.schema_gen` and
verify drift with `just schema-check`, which is part of `just check`.

## Authoring a policy with `$schema`

A policy file may carry a top-level `$schema` property that points at the
hosted raw URL. It is a pure authoring aid:

```json
{
  "$schema": "https://raw.githubusercontent.com/geoder101/perfcheck/refs/heads/main/schemas/v1/perfcheck-policy.schema.json",
  "policy_id": "my-policy",
  "suite_id": "my-suite",
  "policy_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "metrics": [
    {
      "metric_id": "latency_ms",
      "query": "rate(perfcheck_latency_seconds_sum[1m])",
      "unit": "milliseconds",
      "direction": "lower_is_worse",
      "statistic": "p95",
      "practical_threshold": 0.05,
      "step_seconds": 10,
      "rate_window_seconds": 60
    }
  ]
}
```

perfcheck treats `$schema` as metadata only:

- It is stripped before `SuitePolicy.model_validate_json`, so it never blocks
  validation and never affects `policy_content_sha256` or policy identity.
- `perfcheck policy stamp` preserves a present `$schema` verbatim in its
  canonical output.
- `perfcheck policy check` WARNS (the exit status stays `0`) when the pointer
  references an unrecognized perfcheck schema version.

The generated schema separately permits the data-level `$schema` so editors do
not flag it against the strict policy body.
