# perfcheck Repository Guide

`perfcheck` produces reproducible performance-regression evidence for CI.
Keep the public surface CLI-only; internal Python APIs and artifact schemas are
unstable and may change during cleanup. Keep changes within the CLI contract
unless [README's public scope](README.md#scope) changes in the same work.

## README Index

- [Root README](README.md): installation, CLI workflow, scope, and evidence interpretation.
- [Source](src/README.md): module map and artifact flow.
- [Tests](tests/README.md): behavior coverage, fixtures, and test selection.
- [Tools](tools/README.md): repository helpers and evidence handling.
- [Docs](docs/README.md): Diataxis navigation, generated API, and rendering setup.
- [Examples](examples/README.md): ordered executable lessons and lesson setup.
- [Workflows](.github/workflows/README.md): CI, evidence retention, and Pages.

## Change Boundaries

- Before changing command behavior, read all five: `just cli --help`,
  `just cli policy --help`, `just cli collect --help`,
  `just cli summarize --help`, and `just cli compare --help`.
- Start with the test named for the behavior or module being changed.
- Keep credentials out of persisted artifacts, labels, metadata, queries, logs,
  and diagnostics. Review `src/perfcheck/errors.py` and collection logging
  before changing boundary data.
- Don't add undocumented external integrations. The documented scope excludes
  dashboards, databases, DSLs, HTML, and other external integrations.
- Don't overwrite an output path unless the command accepts AND receives
  `--force`. CLI preflight reports existing paths as an input error.
- Preserve canonical serialization and content-hash verification when touching
  policies or artifacts; see `src/perfcheck/storage.py`.

## Commands and Quality Gates

- The [justfile](justfile) is the source of truth for commands; run `just --list`
  for the full set. Use canonical recipes, not hand-assembled substitutes, and
  don't duplicate them in `podman.just`. Use `just build` for distributions.
- Follow [setup](README.md#install) and [configuration](pyproject.toml):
  Python `>=3.14,<3.15`, `uv` package/environment management, `uv_build` backend.
- Use `just sync` for locked dev/docs/examples groups without optional mutmut;
  rerun it after mutation work to restore the ordinary environment.
- Keep Ruff's Python 3.14 target, 88-character lines, and `ALL` rules;
  BasedPyright's `typeCheckingMode = "all"` over `src` and `tests`; and pytest's
  `tests` discovery, strict config/markers, and warnings-as-errors expectations.
- Use `just check` as the standard complete gate: lock verification, format
  check, lint, type checking, tests, executable examples, documentation, and build.
  Keep ordinary `just test` and `just check` coverage-free and mutation-free.
- Opt into `just coverage [pytest args]` for exploratory statement/branch
  reports with no default floor; `just coverage-check` is a zero-argument,
  fresh full-suite 99% combined statement/branch coverage gate.
- Keep `just mutation` an optional Unix-only aggregation pilot: dedicated
  dependency group, one worker, 600-second child budget; refuse nonempty `mutation/`.
  Archive retained evidence outside the checkout before rerunning; then `just sync`.

## Committing

- **Commit when a logical deliverable is ready.** A commit is a self-contained
  unit that builds and passes `just check`. When such a deliverable is complete —
  a finished fix with its tests, a finished feature, a piece of tooling — commit
  it rather than letting it pile up as uncommitted work. Split a change along its
  natural seams (a code fix and the test harness that proves it are two commits);
  never commit half-finished or non-green work.
- **Conventional Commits style.** `<type>(<scope>): <imperative summary>` with
  `feat`/`fix`/`test`/`docs`/`refactor`/`build`/... and a scope naming the affected
  area (e.g. `policy`, `compare`, `docs`, `examples`). Keep the subject imperative and tight; add a
  short body only when the *why* is non-obvious. Never commit secrets.

## Documentation and Hosted Evidence

- Use `just docs-check` for fresh Furo HTML with warnings treated as errors,
  using the docs dependency group. `just docs-preview [port]` runs that build
  before serving `docs/_build/html` (default 8000); stop with Ctrl-C and clean up
  preview processes after QA. Follow the linked README for rendering prerequisites.
- Keep AutoAPI source-parsed over all `src` without importing application modules;
  exclude private/special members. Reference owns generated API navigation.
  Treat generated API RST and built HTML as ignored outputs, not hand-maintained
  sources or promises of Python API compatibility.
- Follow [README evidence guidance](README.md#quality-checks) and its
  [workflow guide](.github/workflows/README.md).
  CI runs `just check` across Linux, macOS, and Windows on every push; the Pages
  site publishes from the default branch. Keep Pages docs-only, including internal
  AutoAPI, never coverage/mutation evidence.

## Hosted schema contract

- The versioned JSON Schema at `schemas/v1/perfcheck-policy.schema.json` is a
  hosted, versioned public contract for the policy file (the only artifact a
  user or AI authors). It is distinct from the still-unstable internal artifact
  and Python schemas; see the Scope carve-out in [README](README.md#scope).
- Versioned schema files are IMMUTABLE. Additive changes go to a new version
  path; breaking changes go to a new major path. Never overwrite a committed
  versioned schema file in place — the `schema-check` drift gate
  (`just schema-check`, part of `just check`) fails on regeneration drift.
- `$schema` is an authoring-only aid. perfcheck strips a data-level
  `$schema` before validation and never lets it affect policy identity or the
  content hash (`policy_content_sha256`). `stamp` preserves a present pointer
  verbatim; `policy check` WARNS when the pointer references an unrecognized
  schema version.
- Hosted raw URLs serve from the default branch. This is a hosted schema
  contract, not a Python-API compatibility promise.

## Optional Podman Safety

- Follow [Podman setup and overrides](README.md#optional-podman-environment);
  the original `justfile` remains authoritative.
- Keep container state separate from host `.venv`; serialize sync/mutation state
  operations and preserve evidence before cleanup.
- Never run concurrent host/container writers to the same `docs/_build/`, `dist/`,
  `coverage/`, or `mutation/`; distinct state volumes don't isolate these outputs.
- Don't claim native Windows compatibility from container checks.
- Keep Windows launch ExecutionPolicy Bypass process-scoped, not machine/user
  policy changes; organization Group Policy can still block execution.
- Keep build/run proxy-environment forwarding disabled (`--http-proxy=false`);
  configure proxy networking deliberately when needed.

## Guide Inheritance

Apply this guide repository-wide. Child `AGENTS.md` files add local rules and
take precedence when more specific. Don't repeat root guidance in child files;
document only the local details needed there.
