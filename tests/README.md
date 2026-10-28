# perfcheck test suite

This directory checks application behavior, CLI outcomes, persisted evidence,
statistics, and the repository's development workflows. The supported public
surface is the CLI; tests of internal Python modules don't promise API stability.
See the [project README](../README.md) for the supported workflow and scope.

## Run from the repository root

The [justfile](../justfile) owns the canonical commands:

```bash
just sync                              # install the ordinary development groups
just test                              # standard test selection
just test -k cli                       # select matching test names/modules
just test tests/test_cli_compare.py     # select one module
just test tests/e2e/test_v1_workflow.py  # select the complete CLI scenarios
just examples-check                    # validate the executable curriculum
```

`just test` forwards pytest arguments and excludes only
[`test_examples.py`](test_examples.py) and
[`test_examples_check.py`](test_examples_check.py). Other examples-related
modules, such as [`test_examples_support.py`](test_examples_support.py) and
[`test_examples_probability.py`](test_examples_probability.py), remain in its
selection. The separate `examples-check` recipe runs the curriculum checker and
its focused tests; see the [lesson index](../examples/README.md).

[Pytest configuration](../pyproject.toml) discovers tests under `tests/`, uses
strict configuration and markers, and treats warnings as errors. Ordinary
`just test` runs without coverage or mutation measurement.

## Find a behavior

These are navigation groups, not separate test markers or execution tiers.
Start with the module named for the behavior, then follow its nearby tests.

| Area | Representative starting points | What they check |
| --- | --- | --- |
| Collection behavior | [Collection orchestration](test_collection_orchestration.py), [sample validation](test_prometheus_sample_validation.py) | Metric collection and classification of malformed upstream evidence. |
| CLI boundaries | [Compare](test_cli_compare.py), [ingress validation](test_cli_ingress_validation.py) | Requested reports, rejected inputs, bootstrap options, and overwrite safety. |
| Artifacts and integrity | [Storage](test_storage.py), [hash oracles](test_hash_oracles.py), [schema boundaries](test_schema_boundary_matrix.py) | Canonical bytes, hashes, source verification, round trips, and invalid evidence. |
| Statistical decisions | [Bootstrap](test_bootstrap.py), [policy outcomes](test_policy_outcomes.py), [suite aggregation](test_suite_aggregation.py) | Seeded resampling, directional bounds, advisory references, and suite verdicts. |
| Numerical edges | [Bootstrap boundaries](test_bootstrap_numerical_boundaries.py), [numerical ingress](test_numerical_ingress.py) | Arithmetic edge cases and invalid sample values at input boundaries. |

## Tooling, workflows, and documentation

The suite also checks the machinery used to build and verify the project:

- [Coverage gate tests](test_coverage_gate.py) exercise fresh evidence handling
  and threshold behavior. [Mutation process tests](test_mutation_process.py)
  check child failure, timeouts, and process cleanup, with platform-specific skips.
- [CI workflow tests](test_ci_workflows.py) inspect workflow configuration.
  [Pages authorization](test_pages_authorization.py) covers deployment guards.
  These checks don't establish that hosted jobs or deployments have run.
- [Rendered documentation](test_docs_html.py) checks site links, navigation, and
  local assets. [Diataxis navigation](test_diataxis_navigation.py) and
  [reference docs](test_reference_docs.py) cover documentation structure.
  The session fixture in [conftest.py](conftest.py) uses
  [docs_build.py](docs_build.py) to build a temporary documentation project.
- [Container contracts](test_container_contract.py) and
  [Podman forwarding](test_podman_forwarding.py) cover the optional adapter.
  See the project README for runtime prerequisites and validation limits.

## Fixtures and support

- [Policy fixtures](fixtures/policy-pass.json), the
  [Prometheus matrix](fixtures/prometheus/matrix.json), and
  [golden verdicts](fixtures/golden/) supply the complete workflow scenarios.
  Pass, fail, and inconclusive each have a policy and golden `suite_status`.
- The [mock Prometheus server](fixtures/mock_prometheus_server.py) serves local
  query-range responses and can echo a token into response metadata for
  redaction checks. It doesn't require a live Prometheus deployment.
- [CLI support](cli_support.py) builds policies, raw runs, summaries, and compare
  inputs. Other focused helpers include [artifact schema support](artifact_schema_support.py)
  and [comparison boundary support](comparison_boundary_support.py).
- [E2E support](e2e/support.py) manages the local server process and resolves
  the generated console-script path for the active platform.

## Distribution and complete CLI E2E

[`test_fresh_wheel.py`](e2e/test_fresh_wheel.py) builds a wheel, installs it in a
clean virtual environment, and probes the installed package and CLI help outside
the checkout with project/import environment overrides removed. A malformed-wheel
case checks that a missing package is detected. Builds and installs may need
network access.

[`test_v1_workflow.py`](e2e/test_v1_workflow.py) instead uses the active environment's
generated console script with a loopback Prometheus fixture. Each scenario runs
`collect`, `summarize`, then `compare`, checks JSON and Markdown report files,
and matches the golden suite verdict with exit status 0, 1, or 2 for pass, fail,
or inconclusive. This exercises the complete CLI workflow, not another clean-wheel install.

## Optional coverage evidence

Use `just coverage` or `just coverage tests/test_cli_compare.py` for exploratory
statement and branch reports with the standard test selection and no default
threshold. `just coverage-check` accepts no arguments and enforces a fresh
full-suite 99% combined gate. Reports go under `coverage/`; installed-wheel
execution isn't claimed as instrumented coverage. See the
[project README](../README.md#coverage-evidence) for interpretation and limits.
