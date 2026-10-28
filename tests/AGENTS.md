# Tests Guide

## Scope

See [README.md](README.md) for the descriptive suite and fixture inventory.

Keep each test beside the behavior or module it exercises, using a
descriptive `test_<behavior>.py` module name rather than grouping unrelated
features. Keep ordinary tests fast, isolated, and focused on one behavior.

`tests/e2e/` owns package and distribution workflow checks. Put installation,
built-wheel, console-script, and other full workflow coverage there, not in
the ordinary test modules.

## Test Shape

- Structure each test with clear `Given`, `When`, and `Then` blocks or comments.
  The `When` is one observable action; the `Then` asserts its contract.
- Favor behavior-oriented assertions over implementation details. Assert the
  public result, artifact contents, error outcome, or rendered report that a
  caller observes.
- Keep setup local when it clarifies the scenario. Use small, typed local
  builders for policies and domain values instead of untyped dictionaries or
  broad shared factories.
- Exercise real application code and temporary filesystem paths for ordinary
  CLI and artifact behavior. At HTTP transport seams, use `httpx2.MockTransport`
  so request and response behavior remains explicit and deterministic.
- Express policy combinations as parametrized matrices. For sampled or random
  behavior, use an explicit seed and assert the resulting deterministic
  outcomes.

## Fixture Contracts

Fixtures are intentionally compact. Extend an existing static policy, golden
report, or Prometheus matrix when possible instead of adding fixture plumbing.

- A policy fixture's query keys must exactly align with the query keys in its
  Prometheus matrix fixture. Keep both sides updated in the same change.
- Golden report fixtures must assert `suite_status`, not only individual metric
  decisions, so suite-level policy outcomes stay covered.
- `fixtures/mock_prometheus_server.py` can echo a configured token in response
  metadata. Preserve that behavior because redaction tests depend on it.
- Keep fixture data focused on one policy outcome or transport scenario. Put
  scenario-specific values in the test when they don't belong in shared data.
