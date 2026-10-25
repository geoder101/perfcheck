# perfcheck

`perfcheck` provides reproducible performance-regression evidence for CI.

## Install

This project requires Python 3.14. Install the application and development tools
with [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
```

Run the CLI through the managed environment:

```bash
uv run perfcheck --help
```

Start with the [Project documentation](docs/index.rst) for a workflow overview
and four Diataxis paths: Tutorials, How-to guides, Reference, and Explanation.
The [Marimo curriculum index](examples/README.md) offers ten executable lessons
in order, from the CLI workflow to statistical mechanics and comparative methods.

The Furo documentation site is optional; it is not needed to run the CLI.
Build it or preview it locally from the repository root:

```bash
just docs-check
just docs-preview        # fresh build, then serve at http://localhost:8000
just docs-preview 8765   # optional port; stop with Ctrl-C
```

These commands use the optional docs dependency group and build into
`docs/_build/html`. Reference includes source-parsed AutoAPI documentation of
internal Python modules, not a supported public Python API.

## Commands

The supported workflow collects a portable raw run, summarizes a verified raw
run, and compares current and baseline evidence under one policy. Use the live
help for each command's required paths and options:

```bash
uv run perfcheck collect --help
uv run perfcheck summarize --help
uv run perfcheck compare --help
```

- `collect` writes one raw run artifact from all metrics in a suite.
- `summarize` writes one canonical summary artifact from a verified raw run.
- `compare` evaluates current and baseline summaries (or raw-run inputs) and
  writes JSON (`--report-json`), Markdown (`--report-md`), or both. At least
  one report output is required; `--json` additionally emits JSON to stdout.

## Quality checks

Run the same local checks before contributing documentation or code:

```bash
just sync
just check
```

`just sync` installs the locked dev/docs/examples groups, excluding optional
mutation tooling (and removes it after a pilot). Ordinary `just test` and
`just check` remain coverage-free and mutation-free.

### Coverage evidence

Coverage is opt-in:

```bash
just coverage
just coverage tests/test_cli_compare.py   # optional pytest selection/arguments
just coverage-check                     # fixed fresh full-suite 99% combined gate
```

This measures statements and branches in `src/perfcheck` using the same test
selection as `just test`, including instrumentable Python subprocesses. Open
`coverage/html/index.html` or inspect `coverage/coverage.json`; combined raw data
is retained at `coverage/.coverage`. These generated outputs are ignored.
`just coverage` is exploratory with no threshold unless explicitly requested.
`just coverage-check` accepts no arguments, clears old reports before measurement,
and enforces 99% combined statements and branches using coverage.py precision
semantics, not an average of percentages or rounded terminal text. Failed tests
or a failed threshold remain failures; early errors may leave reports unavailable.
Coverage records execution, not the strength of assertions. The optional
curriculum remains a separate
`just examples-check` gate, outside this baseline. Fresh-wheel smoke tests still
run in clean application-only environments: they verify packaging functionality
but their installed-wheel execution is not claimed as instrumented coverage.

In addition to coverage.py's default exclusions, reporting excludes audited
exhaustive `case _:` guards immediately followed by `assert_never(...)`.
Ordinary wildcard fallbacks and validation errors remain measured. These
exclusions adjust the statement and branch denominators; they do not execute
more tests or represent additional tested behavior.

The independent Linux CI coverage job retains selected HTML, JSON, hidden raw
`.coverage`, and provenance in an Actions artifact for seven days. Download it
from the run's Actions page; open `html/index.html` and inspect `provenance.json`.
The tested SHA is the actual checkout (a PR merge revision can differ from the
separately labeled PR head). Failed-gate evidence is partial; missing, stale or
invalid reports are unavailable, never replaced with earlier success. Coverage
and mutation evidence are not published on Pages.

### Optional mutation pilot

`just mutation` explicitly installs the dedicated mutation group with pinned
`mutmut==3.8.0`. This Unix-only manual pilot mutates a disposable snapshot of
`src/perfcheck/regression_aggregation.py`, selecting only
`tests/test_suite_aggregation.py`: one worker, 600-second child budget. It does
not mutate checkout sources or run in ordinary checks; Windows is unsupported.

Before a fresh run, inspect and archive the entire existing ignored `mutation/`
directory outside the checkout to a new, unused destination (or remove that exact
directory only if its evidence is no longer needed). A nonempty output is refused;
old results are never reused. Then run:

```bash
just mutation
just sync       # restore the ordinary environment without mutmut
```

Inspect `mutation/status.json`, native JSON statistics, `results.txt`, logs,
manifest and mutated-copy import receipts; these are not native mutmut HTML.
`complete` means a validated nonzero experiment; `invalid` signals infrastructure,
baseline or evidence failure; `incomplete` records an interrupted/budget-limited
experiment. Killed, surviving, timeout and internal-error outcomes are distinct.
Survivors are advisory with no score gate: inspect the saved killed/surviving
diffs and selected-test assertions before deciding whether a test gap exists.
Do not equate guard-removal survival with proven equivalence.

The manual Actions workflow retains approved available evidence and a summary
for seven days, downloadable from its run's artifact list. Unexpected workflow
failure means invalid/incomplete/unavailable infrastructure or evidence, not a
penalty for survivors. It never publishes results on Pages.

### One-time GitHub hosting setup (owner)

The GitHub repository is not yet created; no live site or hosted platform result
is claimed. Pages publishes only the existing Furo/Sphinx documentation, including
source-parsed AutoAPI for internal Python modules. A public documentation site
does not make those modules a supported public Python API.

1. Create the GitHub repository and push this checkout to its actual default branch.
   Enable Actions and allow the workflows' pinned actions under repository or
   organization policy; do not assume the branch is named `main`.
2. Select **Settings > Pages > Build and deployment > Source > GitHub Actions**.
3. Configure the **github-pages** environment's deployment branch restrictions to
   the actual default branch only, with no tags. Required reviewers are optional
   unless the owner requires them; the environment name alone is not protection.
4. On the first default-branch push, verify Linux/macOS/Windows `just check`, the
   independent coverage gate, and downloaded provenance/raw/HTML evidence. These
   hosted results, especially Windows, still require a real run.
5. Manually dispatch the mutation workflow and check its status and downloadable
   seven-day artifacts. Dispatch Pages on the default branch and verify the
   deployment output URL, landing page, nested API pages and CSS/assets.

Pages allows only default-branch pushes/manual dispatches: PRs never deploy,
and non-default branches/tags are denied before dependency installation/build.
Authorization/build use read-only contents permissions; only the dependent deploy
job gets Pages-write/OIDC permissions and consumes the same run's docs artifact.
No PAT or branch-push publishing is needed. The URL comes from deployment output,
not a hardcoded future repository address.

## Scope

Internal implementation may change or be removed during breaking cleanup; this
README does not promise compatibility or stability for internal APIs or artifact
schemas. The supported surface described here is limited to the current CLI
commands. No dashboard, database, DSL, HTML, or other external integrations are
promised.
