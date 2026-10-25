# perfcheck Repository Guide

## Purpose

`perfcheck` produces reproducible performance-regression evidence for CI.
The supported workflow collects a portable raw run, summarizes verified raw
evidence, then compares current and baseline evidence under one policy.

The public surface is the `perfcheck` CLI only. Internal Python APIs and
artifact schemas are unstable and may change during cleanup. See `README.md`
for the supported command workflow and scope.

## Structure

```text
src/perfcheck/   CLI, domain models, collection, evaluation, persistence, reports
tests/           behavioral, CLI, artifact, policy, and regression coverage
docs/            project-first Diataxis documentation and generated internal API
examples/        ten ordered executable Marimo lessons and local fixtures
pyproject.toml   package metadata and enforced tool configuration
justfile         canonical developer commands
README.md        installation, CLI workflow, and public-surface statement
```

## Where to Look

- CLI entry point and command boundary: `src/perfcheck/cli.py`.
  The console script maps `perfcheck` to `perfcheck.cli:app`.
- Shared strict Pydantic base and semantic model types: `src/perfcheck/model_types.py`.
  `StrictModel` is the base for validated public models.
- Suite policy models and policy identity logic: `src/perfcheck/policy_models.py`
  and `src/perfcheck/policy.py`.
- Prometheus collection orchestration: `src/perfcheck/collection_service.py`.
  It collects policy metrics into one raw run, retaining partial failures.
- Persisted evidence and integrity verification: `src/perfcheck/storage.py`.
  Artifacts use canonical JSON and content hashes.
- Regression decision facade: `src/perfcheck/regression.py`.
  It applies policy to validated cohorts.
- Report assembly and renderers: `src/perfcheck/report_assembly.py` and the
  report modules. The CLI writes JSON and Markdown reports.
- Tests: start with the test named for the behavior or module being changed.
  `pyproject.toml` declares `tests` as the pytest test path.
- Documentation entry point: `docs/index.rst`. Diataxis sources live in
  `docs/tutorials/`, `docs/how-to/`, `docs/reference/`, and `docs/explanation/`.
  The runnable curriculum is indexed in `examples/README.md`, lessons 01–10.
- Internal API reference: `docs/conf.py` configures source-parsed AutoAPI over
  all of `src`; it does not import application modules. Reference owns the
  generated API navigation; private/special members are excluded. Generated
  API RST and built HTML are ignored outputs, not hand-maintained sources or
  promises of Python API compatibility.

## Artifact Flow

1. `collect` writes a raw run artifact from suite metrics.
2. `summarize` writes a canonical summary from a verified raw run.
3. `compare` accepts summaries or raw-run inputs, evaluates policy, and writes
   JSON plus Markdown reports.

Read CLI help before changing command behavior:

```bash
just cli --help
just cli collect --help
just cli summarize --help
just cli compare --help
```

## Environment and Build

- Python: `>=3.14,<3.15`.
- Package and environment manager: `uv`.
- Build backend: `uv_build`.
- Sync development dependencies: `just sync`.
- Ordinary sync uses locked dev/docs/examples groups, excluding optional mutmut;
  rerun it after mutation work to restore the ordinary environment.
- Build distributions: `just build`.
- Optional documentation: `just docs-check` builds fresh Furo HTML with warnings
  treated as errors using the docs dependency group. `just docs-preview [port]`
  runs that build before serving `docs/_build/html` (default port 8000); stop
  with Ctrl-C and clean up preview processes after QA.

## Quality Gates

`pyproject.toml` enforces the following:

- Ruff targets Python 3.14, uses 88-character lines, and selects `ALL` rules.
- BasedPyright runs with `typeCheckingMode = "all"` over `src` and `tests`.
- Pytest uses strict config and markers, with all warnings treated as errors.

Use `just` commands, not hand-assembled substitutes:

```bash
just test
just format-check
just lint
just typecheck
just lock-check
just build
just examples-check
just docs-check
just check
```

`just check` is the standard complete gate: lock verification, format check,
lint, type checking, tests, executable examples, documentation, and build.
It and `just test` remain coverage-free and mutation-free. Opt-in commands:

- `just coverage [pytest args]`: exploratory statement/branch reports, no default floor.
- `just coverage-check`: zero-argument fresh full-suite 99% combined coverage gate.
- `just mutation`: optional Unix-only aggregation pilot; installs its dedicated
  group, uses one worker/600-second child budget, and refuses nonempty `mutation/`.
  Archive retained evidence outside the checkout before rerunning; then `just sync`.

README owns evidence interpretation and the one-time GitHub Pages owner checklist.
Hosted CI/platform/deployment results remain pending until a real repository run;
Pages is docs-only, including internal AutoAPI, never coverage/mutation evidence.

## Root Rules

- Keep credentials out of persisted artifacts, labels, metadata, queries, logs,
  and diagnostics. Review `src/perfcheck/errors.py` and collection logging
  before changing boundary data.
- Don't add undocumented external integrations. The documented scope excludes
  dashboards, databases, DSLs, HTML, and other external integrations.
- Don't overwrite an output path unless the command accepts and receives
  `--force`. CLI preflight reports existing paths as an input error.
- Preserve canonical serialization and content-hash verification when touching
  policies or artifacts. See `src/perfcheck/storage.py`.
- Keep changes within the CLI contract unless the README's public scope changes
  in the same work.

## Guide Inheritance

This file defines repository-wide guidance. Child `AGENTS.md` files add local
rules for their directory and take precedence when more specific. Don't repeat
this root guide in child files; document only the local details needed there.
