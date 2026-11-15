# perfcheck source guide

The [perfcheck package](perfcheck/) implements reproducible performance-regression
evidence for CI. Its workflow collects a portable raw run, summarizes verified
evidence, then compares current and baseline evidence under one policy.

The `perfcheck` CLI is the only supported public surface. Internal Python APIs
and artifact schemas are unstable and may change or be removed during cleanup.
This guide is a reading map, not a Python API compatibility promise. See the
[project README](../README.md) for installation, supported commands, and scope.

## Navigate by workflow

- **Command boundary:** [cli.py](perfcheck/cli.py) defines the `collect`,
  `summarize`, and `compare` commands. The console entry point is
  `perfcheck.cli:app`, declared in [pyproject.toml](../pyproject.toml).
  [cli_services.py](perfcheck/cli_services.py) handles shared orchestration,
  input loading, output preflight, and summary derivation.
- **Collection:** [collection_service.py](perfcheck/collection_service.py)
  coordinates suite-wide collection and retains per-metric failures in a raw
  run. [prometheus.py](perfcheck/prometheus.py) handles range-query transport;
  its companion ingress, response, and validation modules check external data
  and redact sensitive diagnostics.
- **Evidence and summaries:** [storage.py](perfcheck/storage.py) owns canonical
  JSON, atomic artifact writes, content hashes, and integrity verification.
  [artifact_models.py](perfcheck/artifact_models.py),
  [run_models.py](perfcheck/run_models.py), and
  [summary_models.py](perfcheck/summary_models.py) describe evidence shapes.
  [summarize.py](perfcheck/summarize.py) applies eligibility rules and selects a
  per-run statistic using [summary_statistics.py](perfcheck/summary_statistics.py).
- **Policy and regression:** [policy_models.py](perfcheck/policy_models.py) and
  [policy.py](perfcheck/policy.py) define suite rules and comparison identity.
  [regression.py](perfcheck/regression.py) evaluates validated cohorts through
  per-metric decisions and suite aggregation. [bootstrap.py](perfcheck/bootstrap.py)
  and its companion modules provide resampling and confidence calculations.
- **Reporting:** [report_assembly.py](perfcheck/report_assembly.py) combines
  policy, cohorts, and outcomes into a report. [report_json.py](perfcheck/report_json.py)
  and [report_markdown.py](perfcheck/report_markdown.py) render the CLI outputs.
- **Shared vocabulary:** [model_types.py](perfcheck/model_types.py) provides
  `StrictModel`, semantic types, and enums; [errors.py](perfcheck/errors.py)
  defines classified failures used across boundaries.

## Suggested reading route

1. Start with the [workflow documentation](../docs/index.rst) or the
   [executable lessons](../examples/README.md) to see what the CLI produces.
2. Follow one command from `cli.py` into `cli_services.py`. For `collect`,
   continue into `collection_service.py` and the Prometheus transport.
3. Trace a raw run through `storage.py`, then summary derivation and
   `summarize.py`. Notice which failures and eligibility reasons are retained.
4. Follow `compare` into policy checks, `regression.py`, bootstrap calculations,
   and report assembly. Compare the JSON and Markdown renderers last.
5. Read the matching behavior tests in [tests/](../tests/) alongside each stage.
   Before editing package code, consult the local [package guide](perfcheck/AGENTS.md).

## Useful commands

Run all commands from the repository root, not from `src/`. The
[justfile](../justfile) is the command reference; the project README documents
native documentation-build prerequisites.

```bash
just sync                  # install locked development, docs, and lesson tools
just cli --help
just cli policy --help
just cli collect --help
just cli summarize --help
just cli compare --help
just test                  # standard tests, without coverage or mutation
just format-check
just lint
just typecheck
just check                 # full standard gate, including examples, docs, build
```

When tracing a specific behavior, pass its test path to `just test`, for example
`just test tests/test_summarize.py`. Use `just examples-check` for executable
lessons, `just docs-check` for documentation, and `just build` for distributions.
