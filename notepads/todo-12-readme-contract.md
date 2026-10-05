# Todo 12 README contract evidence

## Red / green

- Initial stale-claim probe: `uv run pytest tests/test_readme_contract.py::test_readme_does_not_claim_commands_are_future_work -q`
  passed because the old claim was split across two Markdown lines.
- The test normalizes whitespace before checking the rendered claim. The same
  command then failed with `commands will be added` in the README, proving the
  stale documentation defect.
- After the README update: `uv run pytest tests/test_readme_contract.py -q` —
  `2 passed in 0.01s`.

## Manual CLI documentation QA

- `uv run perfcheck collect --help` — available; describes raw run collection.
- `uv run perfcheck summarize --help` — available; describes canonical summary
  creation from a verified raw run.
- `uv run perfcheck compare --help` — available; describes comparison of
  verified summaries or raw-run inputs.

The command names and descriptions match the README.

## Quality gates

- `uv run pytest` — `139 passed in 26.12s`.
- `uv run ruff check .` — `All checks passed!`.
- `uv run basedpyright` — `0 errors, 0 warnings, 0 notes`.
- `lsp_diagnostics tests/test_readme_contract.py` could not run because the
  basedpyright language server is not installed (installation was previously
  declined); the requested CLI type check passed.

## Negative probes

- Dirty-worktree probe found pre-existing untracked `.omo/run-continuation/`
  files and `tests/e2e/test_fresh_wheel.py`; none were modified.
- Misleading-success probe found the first raw-string check missed a Markdown
  line break; whitespace normalization fixed the test before the green run.
- The contract test is local, deterministic text inspection with no time,
  network, or order dependency.
- No generated test artifacts required cleanup.
