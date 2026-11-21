# CI workflows

This directory holds the GitHub Actions workflows for perfcheck.
This file is the map of what each workflow does; the YAML files are the truth.

## Shared setup action

The composite action at [`.github/actions/setup`](.github/actions/setup/action.yml)
installs the pinned toolchain (`setup-uv`, `setup-just`) and keeps it declared and
bumped in one place. Each consumer performs its **own** `actions/checkout@v7.0.1` at
the event SHA, then calls the composite with `uses: ./.github/actions/setup`. Keeping
checkout inline in the consumers while sharing one toolchain definition keeps the
checkout pinned to an immutable SHA (enforced by `tests/test_ci_workflows.py`) and the
toolchain versioned in a single place.

Call it with `uses: ./.github/actions/setup`; pass `just-version: "1.59.0"` where
`just` is needed (it is the default, so most consumers omit it).

## Job timeouts and artifact warnings

Every job carries a `timeout-minutes` ceiling, and every upload uses
`if-no-files-found: warn` so a missing artifact surfaces as a warning rather
than a silent pass.

## `ci.yml` — CI

**Triggers:** `pull_request` and `push` (any branch).

| Job | Runs on | What it proves |
|-----|---------|----------------|
| `check (ubuntu-latest)` | Linux | `just check`: lock/schema, format/lint/types, tests, examples, strict docs, and wheel/sdist builds. |
| `check (macos-latest)` | macOS | The same full native gate, without weakening checks. |
| `check (windows-latest)` | Windows | The same full native gate, without weakening checks. |
| `coverage` | `ubuntu-latest` | The fresh full-suite combined coverage gate (`just coverage-check`, fixed 99% threshold) passes, then exports approved evidence. |

**Artifact:** `coverage-evidence-${{ github.run_id }}-${{ github.run_attempt }}`, uploaded with
`if: always()` so it exists even when the gate fails. Contents: `coverage/evidence/html/`
(the HTML report), `coverage/evidence/coverage.json` (machine-readable report),
`coverage/evidence/.coverage` (the raw data file), and `coverage/evidence/provenance.json`.
**Retention: 7 days.** Failed-gate evidence is partial, and unavailable reports aren't a
passing measurement. See [coverage evidence](../../README.md#coverage-evidence) for
interpretation and local output paths.

CI also exposes `workflow_call` so Releases depend on the identical matrix and
coverage gate. Python 3.14 is the sole supported minor version, matching metadata;
there is no additional Python-version axis. Shared rendering setup provisions
Linux TeX/browser libraries, macOS MacTeX, or Windows MiKTeX, plus locked Mermaid
and Chrome. Optional Unix-only mutation/process tests and tests requiring absent
external tools retain their explicit platform/resource skips; the full gate runs
on each OS. No live external service is needed by application tests; Prometheus
fixtures use loopback or mock transports.

Warnings remain errors except two exact Marimo 0.25.2 import-time Windows asyncio
policy deprecations. This owner-approved upstream compatibility exception is
scoped to `marimo._islands._island_generator`; remove it when Marimo migrates away
from the deprecated policies. It does not skip notebook tests or application
warnings.

## `pages.yml` — Documentation Pages

**Triggers:** `push` to `main`.

| Job | Runs on | What it proves |
|-----|---------|----------------|
| `authorize` | `ubuntu-latest` | Explicitly requires a push to `refs/heads/main` and repository default branch `main`. |
| `build` | `ubuntu-latest` | Checks out the event SHA (`persist-credentials: false`), then proves the strict docs build (`just docs-check`, `-W`) passes. Uploads `docs/_build/html` as the `github-pages` artifact via `upload-pages-artifact`. |
| `deploy` | `ubuntu-latest` | Reads the `github-pages` artifact by name and deploys it via the `deploy-pages` action in the `github-pages` environment (no separate download or configure step). The site URL is the **deployment output** (`steps.deployment.outputs.page_url`), surfaced on the environment — it is not hardcoded anywhere. |

**Concurrency:** group `github-pages`, `cancel-in-progress: false` — deployments
queue rather than cancel each other.

### Pages authorization model

- **Default-branch-only.** The trigger fires on pushes to `main` only, so pull
  requests and non-default branches build and deploy nothing.
- **PRs never deploy.** `pages.yml` does not trigger on `pull_request` (the
  trigger is `main`-only), so pull requests build and deploy nothing; they are
  checked by `ci.yml` only.
- **The URL comes from deployment output.** The `deploy` job's
  `environment.url` is `steps.deployment.outputs.page_url`, so the canonical
  site URL is whatever GitHub Pages reports for the deployment — never an
  invented or hardcoded value.
- **Environment gate.** `deploy` runs in the `github-pages` environment, which
  the repository owner restricts to the default branch. The job needs
  `pages: write` and `id-token: write`; the workflow-level permission is
  `contents: read`.

Publication is docs-only: Furo/Sphinx HTML, including source-parsed internal
AutoAPI reference. Coverage and mutation evidence never go to Pages.

## `release.yml` — Release

**Triggers:** `push` to `main` only. Workflow-level permission: `contents: read`.

| Job | Runs on | What it proves |
|-----|---------|----------------|
| `test` | Reusable CI | All three native `just check` jobs plus the independent 99% coverage gate must pass on the pushed commit. |
| `publish` | `ubuntu-latest` | Requires default-branch `main` push and human `release` environment approval. Reads the version from `pyproject.toml`, builds wheel and sdist with `just build`, and creates a GitHub Release targeting the exact tested SHA. Existing releases are left unchanged; existing tags without releases fail for inspection. |

Only the `publish` job receives `contents: write` (required to open the release);
the `test` job and all other workflows stay read-only. The GitHub Release is gated
on the default branch and the `release` environment, which requires a human
reviewer and disallows administrator bypass. Releases are serialized with
`cancel-in-progress: false`; no package-registry publication is configured.

## `mutation.yml` — manual advisory pilot

**Triggers:** `workflow_dispatch` only.

| Job | Runs on | What it proves |
|-----|---------|----------------|
| `mutation` | `ubuntu-latest` | Runs the bounded, single-worker `just mutation` pilot against an isolated aggregation-module snapshot with selected tests. Survivors are advisory, with no score gate. |

This optional experiment targets an isolated aggregation-module snapshot with
selected tests, not the whole application. Infrastructure failures and invalid,
incomplete, or unavailable evidence aren't passing experiments. Approved available
evidence is retained for seven days in the run's Actions artifacts; the workflow
also writes a summary.

Don't add mutation to routine checks. Read the root
[optional mutation pilot](../../README.md#optional-mutation-pilot) guidance before
running locally, especially how to preserve existing evidence and restore the
ordinary environment afterward.

## Local smoke test with `act`

Testing here is a two-layer strategy. The static policy tests in
`tests/test_ci_workflows.py` enforce the invariants that `act` cannot check: every
hosted action is pinned to an immutable commit SHA with a matching release-tag
comment, and no forbidden token leaks into a workflow. Those two tests are the
authority on pinning. `act` ([nektos/act](https://github.com/nektos/act)) is a
complementary tool, it renders the workflows and lets you iterate locally before
pushing.

The verified commands, run from the repo root:

- `gh act --version`: confirm `act` is installed.
- `gh act -l`: enumerate every job across all four workflows. This is the local
  gate. It must show each job once (no duplicate job names).
- `gh act -n -W .github/workflows/ci.yml -P default=catthehacker/ubuntu:22.04`:
  dry-run the CI workflow against a container image without touching GitHub.

Container socket. `act` runs each job in a container, so the dry-run needs a
reachable docker/podman socket. Point it at one with `DOCKER_HOST`, for example:

```bash
export DOCKER_HOST=unix://run/podman.sock
gh act -n -W .github/workflows/ci.yml -P default=catthehacker/ubuntu:22.04
```

## Keeping action pins in sync

Every hosted action is pinned to an immutable commit SHA. When you bump an action
version, update its entry in the `EXPECTED_SHA/EXPECTED_TAG` tables in
`tests/test_ci_workflows.py` alongside the workflow, or the SHA-pin test fails.
