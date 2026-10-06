# E2E Guide

## Scope

This directory proves distribution isolation checks and complete CLI workflows.
The supported public surface is the `perfcheck` CLI.
Add coverage here only when a change affects wheel installation, the generated
console command, or an end-to-end `collect` through `compare` outcome.

Keep unit, CLI boundary, artifact, policy, and fixture-detail coverage outside
this directory. Do not use E2E tests for internal implementation changes.

## Fresh Wheel Isolation

`test_fresh_wheel.py` verifies the built distribution, not the checkout.

- Build a wheel into a temporary artifact directory.
- Create a clean virtual environment and install that wheel into it.
- Remove `PYTHONHOME`, `PYTHONPATH`, `UV_PROJECT`, `UV_WORKING_DIRECTORY`, and
  `VIRTUAL_ENV` from the process environment.
- Run from outside the checkout. Probe the installed interpreter with
  `-I -c "import perfcheck"` to confirm wheel isolation and package presence,
  not a supported public Python surface, then invoke `perfcheck --help`.
- Bound each build, install, import, and CLI process to 30 seconds.
- Preserve the malformed-wheel probe. Removing the package from a wheel must
  make the installed import fail.

Do not accept a passing probe that can import source-tree code, an editable
installation, or an active project virtual environment.

## Workflow Scripts

`test_v1_workflow.py` runs `wheel-pass.sh`, `wheel-fail.sh`, and
`wheel-inconclusive.sh` against the local Prometheus fixture.

- Start `tests/fixtures/mock_prometheus_server.py` with `--port 0`.
- Read the chosen endpoint from the fixture server's stdout.
- Set `PERFCHECK_BIN`, `PERFCHECK_PROMETHEUS_URL`, and `PERFCHECK_SMOKE_DIR`.
- Each script must execute `collect`, then `summarize`, then `compare` using
  temporary output paths.
- `compare` must write both JSON and Markdown reports.
- The scripts assert verdict exits only: pass `0`, fail `1`, inconclusive `2`.

Fixture scripts, their policies and matrices, and golden `suite_status` values
are repository E2E test contracts. Change them only with an intentional CLI
workflow contract change, and keep the script outcome and golden status aligned.

## Test Additions

Prefer the existing three verdict scripts and fixture server. Add a new E2E
scenario only when no smaller distribution or complete-flow contract can prove
the behavior. Assert the installed command's exit status, produced artifacts,
and report formats, never private Python APIs or implementation details.
