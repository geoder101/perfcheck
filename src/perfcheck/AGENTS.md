# perfcheck Package Guide

See the [source guide](../README.md) for workflow and module navigation.

## Package Boundaries

- Keep `cli.py` at the command boundary. Put command orchestration and file
  preflight in `cli_services.py`.
- Keep artifact shapes in `artifact_models.py`, `summary_models.py`, and related
  `*_models.py` modules. Keep parsing and cross-artifact checks in
  `artifact_validation.py` and `storage.py`.
- Put Prometheus transport safety and response parsing in `prometheus.py`,
  `prometheus_ingress.py`, `prometheus_response.py`, and
  `prometheus_validation.py`. `collection_service.py` coordinates suite-wide
  collection and retains per-metric failures.
- Keep policy identity and metric rules in `policy.py` and `policy_models.py`.
  Keep resampling and confidence logic in `bootstrap.py`, `bootstrap_sampling.py`,
  `bootstrap_reference.py`, and `bootstrap_validation.py`; keep cohort decisions
  in `regression.py` and `regression_aggregation.py`.
- Keep metric eligibility and calculation in `summarize.py` and
  `summary_statistics.py`. Assemble reports in `report_assembly.py` and render
  them through `report_json.py` and `report_markdown.py`.

## Central Contracts

- Derive persisted artifact, policy, and report schemas from `StrictModel` in
  `model_types.py`; represent semantic values with the existing typed aliases
  and enums instead of primitive substitutions.
- Raise or return the typed failures defined in `errors.py` and the applicable
  result models. Do not replace classified failure data with ad hoc strings.
- `storage.py` owns canonical JSON, artifact envelopes, content hashes, and
  verification. Preserve canonical serialization and verify hashes before
  consuming raw runs or summaries.

## External Ingress and Secrets

- Treat Prometheus URLs, queries, response bodies, and environment tokens as
  untrusted. Preserve endpoint checks in `prometheus.py`, especially rejection
  of credentials, query strings, and fragments.
- Keep external diagnostics and credential redaction in
  `prometheus_ingress.py` and `prometheus_response.py`; use `errors.py` only
  for classified typed failures. Never persist or expose credentials in
  artifacts, labels, provenance, exceptions, logs, or reports.

## Targeted Tests

- Add artifact and integrity coverage in the matching artifact, storage, or
  validation tests; add transport, endpoint, and redaction coverage in Prometheus tests,
  including `tests/test_prometheus_query_range.py`.
- Add policy, bootstrap, regression, summary, or report coverage in the test
  module named for the changed behavior.
- For public CLI semantics, parsing, options, messages, output-path handling,
  or exit behavior, add or update the corresponding CLI command test.
