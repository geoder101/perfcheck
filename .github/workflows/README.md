# Workflow map

These workflows check the project, retain quality evidence, and publish docs.
The YAML files are the source of truth for triggers, action tags, and tool versions.
Actions currently use exact release tags, not full commit-SHA pins or floating
major tags. Source checkouts still use the event SHA, not a moving branch name,
and disable persisted checkout credentials.

## CI: standard checks and coverage

[ci.yml](ci.yml) runs on pushes and pull requests with read-only contents access.

- The Python 3.14 matrix runs `just check` on Linux, macOS, and Windows.
  It provisions the locked Python groups and documentation rendering tools first.
- `just check` covers lock verification, schema drift check, formatting, lint,
  types, tests, executable examples, strict documentation builds, and
  distribution builds. It's coverage-free and mutation-free.
- A separate Linux job runs `just coverage-check`, the fresh full-suite
  99% combined statement-and-branch gate. It doesn't depend on the matrix job.
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

Follow the root [owner checklist](../../README.md#one-time-github-hosting-setup-owner)
for repository settings, default-branch-only environment restrictions, and first
run verification. Hosted CI/platform runs and Pages deployment remain unverified
until real repository runs establish their results; this map claims no live site.

## Local equivalents and guidance

Run commands from the repository root, not this directory. The
[root README](../../README.md#quality-checks) lists native rendering prerequisites;
the [justfile](../../justfile) owns the recipes.

```bash
just sync
just docs-tools       # explicit native renderer setup, not needed in the container
just check            # standard CI matrix checks on your local platform
just coverage-check   # separate fresh coverage gate
just docs-check       # local documentation build, not a deployment
```

For the optional Unix-only pilot, follow the linked evidence-preservation steps,
then run `just mutation` and `just sync` to restore ordinary dependencies.
Local success doesn't establish hosted or cross-platform success.

See [AGENTS.md](../../AGENTS.md) for repository-wide contributor rules and the
[examples index](../../examples/README.md) for the executable CLI curriculum
checked by `just examples-check` as part of `just check`.
