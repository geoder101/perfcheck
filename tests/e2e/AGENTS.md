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

## Workflow Scenario Matrix

`test_v1_workflow.py` defines a typed Python scenario matrix for pass, fail,
and inconclusive verdicts. It uses the shared `tests/e2e/support.py` helpers,
which start the local Prometheus fixture through `sys.executable` and locate
the generated console command.

- Invoke that command with argument vectors, never through a shell.
- For every scenario, execute `collect`, then `summarize`, then `compare` with
  temporary output paths.
- `compare` must write JSON and Markdown reports and exit with pass `0`, fail
  `1`, or inconclusive `2`.
- Assert the produced report files and compare each JSON report's `suite_status`
  with its golden fixture.

The scenario matrix, policies, Prometheus matrix, and golden `suite_status`
values are repository E2E contracts. Add a scenario only when no smaller
distribution or complete-flow contract can prove the behavior. Assert the
installed command's exit status and public artifacts, never private Python APIs
or implementation details.
