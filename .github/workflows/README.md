# Workflow map

These workflows check the project, retain quality evidence, publish documentation,
and publish releases on the default branch. The YAML files are the source of truth
for triggers, action tags, and tool versions.
Actions are pinned to immutable commit SHAs with release tags in comments, not
floating major tags. Source checkouts still use the event SHA, not a moving
branch name, and disable persisted checkout credentials.

## CI: fast gate, merge-time check, and coverage

[ci.yml](ci.yml) runs on pushes, pull requests, a nightly schedule, and manual
dispatch, always with read-only contents access. It splits verification into three
Linux jobs, cheapest first.

- The fast gate runs `just fast-check` on every push and pull request. It exercises
  lock verification, schema drift check, formatting, lint, types, tests, and
  executable examples — everything except the docs render. It's the cheap, always-on
  gate and is coverage-free and mutation-free.
- After something reaches the default branch (a merge, a direct push, or a manual
  dispatch from the default branch), the full-check job runs `just check`, adding
  strict documentation builds and distribution builds on top of the fast gate. On
  pull requests and schedules this job is skipped.
- A scheduled job (plus manual dispatch) runs `just coverage-check`, the fresh
  full-suite 99% combined statement-and-branch gate. It runs off the push/PR path
  and doesn't depend on the other jobs.
- Evidence export is attempted even after gate failure. Approved available
  HTML, JSON, hidden raw `.coverage`, and provenance are retained for seven days.

Download evidence from the run's Actions artifact list. The tested SHA records
the actual checkout; a pull request merge revision can differ from its separately
labeled head SHA. Failed-gate evidence is partial, and unavailable reports aren't
a passing measurement. See [coverage evidence](../../README.md#coverage-evidence)
for interpretation and local output paths.

## Mutation: manual advisory pilot

[mutation.yml](mutation.yml) runs only through manual `workflow_dispatch` on
Linux. It verifies a clean event-SHA checkout and fresh output locations before
running the bounded, single-worker `just mutation` pilot.

This optional experiment targets an isolated aggregation-module snapshot with
selected tests, not the whole application. Survivors are advisory, with no score
gate. Infrastructure failures and invalid, incomplete, or unavailable evidence
aren't passing experiments. Approved available evidence is retained for seven
days in the run's Actions artifacts; the workflow also writes a summary.

Don't add mutation to routine checks. Read the root
[optional mutation pilot](../../README.md#optional-mutation-pilot) guidance before
running locally, especially how to preserve existing evidence and restore the
ordinary environment afterward.

## Pages: authorized documentation publication

[pages.yml](pages.yml) receives push and manual-dispatch events, but authorizes
only the repository's actual default branch. Pull requests never deploy;
non-default branches and tags are rejected before dependency installation or
build. Don't assume the default branch is named `main`.

Authorization and build have read-only contents permissions. The build checks
out the authorized event SHA, verifies that SHA and a clean tree, then runs a
fresh `just docs-check` and validates the publication tree. Only the dependent
deploy job receives `pages: write` and `id-token: write`; it uses the same run's
`github-pages` artifact and environment. The site URL comes from deployment output.

Publication is docs-only: Furo/Sphinx HTML, including source-parsed internal
AutoAPI reference. Coverage and mutation evidence never go to Pages. Internal
Python modules don't become a supported public API through publication.

Hosted CI runs on every push and pull request, and the Pages site publishes from
the default branch under the default-branch-only environment restriction.

## Release: GitHub release

[release.yml](release.yml) triggers only on pushes to the default branch and runs
a quality gate before anything is built or published.

- `test` runs on `ubuntu-latest` with read-only contents. It runs `just check` (the
  full gate: lock, schema drift, format, lint, types, tests, examples, docs render,
  and build) on the pushed commit; nothing publishes until it is green.
- `publish` needs `test`, runs only on `push` to the default branch, and runs in the
  `release` environment. It syncs and builds the wheel with `uv build`, then creates
  (or updates, with `--clobber`) a GitHub Release tagged `v<version>` from the wheel
  filename using the repository's built-in token.

Only the `publish` job receives `contents: write` (required to open the release); the
`test` job and all other workflows stay read-only. The GitHub Release is gated on the
default branch and the `release` environment; the `release` environment can
additionally require a reviewer.

## Local equivalents and guidance

Run commands from the repository root, not this directory. The
[root README](../../README.md#quality-checks) lists native rendering prerequisites;
the [justfile](../../justfile) owns the recipes.

```bash
just sync
just docs-tools       # explicit native renderer setup, not needed in the container
just fast-check       # fast CI gate (excludes the docs render)
just check            # full local verification (adds docs render and build)
just coverage-check   # full combined coverage gate
just docs-check       # local documentation build, not a deployment
```

For the optional Unix-only pilot, follow the linked evidence-preservation steps,
then run `just mutation` and `just sync` to restore ordinary dependencies.
Local success doesn't establish hosted or cross-platform success.

See [AGENTS.md](../../AGENTS.md) for repository-wide contributor rules and the
[examples index](../../examples/README.md) for the executable CLI curriculum
checked by `just examples-check` as part of `just check`.
