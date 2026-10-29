# perfcheck

`perfcheck` provides reproducible performance-regression evidence for CI.

## Install

For a native checkout, install Python 3.14,
[Just](https://just.systems/man/en/chapter_4.html), and
[uv](https://docs.astral.sh/uv/). Just is the project's task runner; uv is the
underlying Python package and environment manager. Run these commands from the
repository root to set up the contributor environment:

```bash
just sync
```

This installs the application and locked dev/docs/examples groups, excluding
optional mutation tooling. It is the contributor setup, not a minimal CLI install.
The installed `perfcheck` CLI does not require Just.

Run the CLI through the managed environment:

```bash
just cli --help
```

Use Just recipes for covered tasks. If Just isn't available, inspect `justfile`
for the underlying commands rather than maintaining a separate manual checklist.
Use direct commands only for tooling without a recipe or when necessary to
preserve quoted argument boundaries or the application's exit status.

Start with the [Project documentation](docs/index.rst) for a workflow overview
and four Diataxis paths: Tutorials, How-to guides, Reference, and Explanation.
The [Marimo curriculum index](examples/README.md) offers ten executable lessons
in order, from the CLI workflow to statistical mechanics and comparative methods.
Choose a beginner, practitioner, or deep-dive route in
[Learning paths](docs/explanation/learning-paths.rst). The routes connect the
probability, experimental-design, inference/power, and multiple-testing chapters
to interactive labs 06–10 and the lesson 05 CLI capstone. The
[performance verification case study](docs/tutorials/performance-verification-case-study.rst)
walks through actual artifacts and CI outcomes; teaching methods don't add
production decision engines.

The Furo documentation site is optional; it is not needed to run the CLI.
Build it or preview it locally from the repository root:

```bash
just docs-tools         # explicit native provisioning; requires Node 24.18.0 and npm
just docs-check
just docs-preview        # fresh build, then serve at http://localhost:8000
just docs-preview 8765   # optional port; stop with Ctrl-C
```

These commands use the optional docs dependency group and build into
`docs/_build/html`. Reference includes source-parsed AutoAPI documentation of
internal Python modules, not a supported public Python API.
`docs-check` cleans Sphinx's build output before its strict build, so SVGs cannot
be reused across renderer configuration changes. Builds never install JS tools
or browsers implicitly.

Diagrams use the docs-only `sphinxcontrib-mermaid==2.1.1` extension with
`mermaid_output_format = "svg"` and `mermaid_cmd_shell = False`: Sphinx invokes
the shell-free Python launcher in `tools/mermaid.py` to render at build time.
`just docs-tools` runs `npm ci --prefix tools/docs --ignore-scripts`, then explicitly
installs Puppeteer's Chrome. The lockfile fixes Mermaid CLI 12.0.0 and Puppeteer
25.16.0; native builders need Node 24.18.0, npm, and Chrome's platform libraries.
Alternatively, an existing compatible POSIX `mmdc` on `PATH` (including a
Bun-installed global command) is used when local tools are absent. It is not
installed or changed by the build. Windows uses Node and the direct JS entry
point, never a `.cmd` shim. An explicit `PERFCHECK_MERMAID_CLI` can select an
existing absolute JS entry point instead of the local installation.

Equation rendering uses Sphinx's built-in `imgmath`: documentation builders need
LaTeX (including AMS and preview packages) and `dvisvgm` on `PATH`. The generated
diagrams and equations are local SVG assets (diagrams embedded via `object`);
readers need no JavaScript, Node, Chrome, TeX, or CDN connection to view them.
The locked npm tree currently reports two low-severity audit findings for
Mermaid CLI and its KaTeX dependency (GHSA-238p-pmpm-9mq7). These are build tooling,
not application dependencies; no automatic `npm audit fix` is applied.

## Commands

The supported workflow collects a portable raw run, summarizes a verified raw
run, and compares current and baseline evidence under one policy. Use the live
help for each command's required paths and options:

```bash
just cli collect --help
just cli summarize --help
just cli compare --help
```

- `collect` writes one raw run artifact from all metrics in a suite.
- `summarize` writes one canonical summary artifact from a verified raw run.
- `compare` evaluates current and baseline summaries (or raw-run inputs) and
  writes JSON (`--report-json`), Markdown (`--report-md`), or both. At least
  one report output is required; `--json` additionally emits JSON to stdout.

## Quality checks

Run the same local checks before contributing documentation or code:

For native builds, run `just docs-tools` once on first setup or when updating the
locked documentation tooling, before `just check` (see the prerequisites above).
The container image is already provisioned; do not run `docs-tools` there or
download an unused Chrome.

```bash
just sync
just check
```

`just sync` installs the locked dev/docs/examples groups, excluding optional
mutation tooling (and removes it after a pilot). Ordinary `just test` and
`just check` remain coverage-free and mutation-free.

### Optional Podman environment

`podman.just` forwards to the original `justfile`, which remains authoritative.
The host needs Just >=1.57, Podman, and `sh` on Linux or Windows PowerShell on
Windows; host Python, uv, and TeX aren't required. Run from the checkout root:

```bash
just -f podman.just build
just -f podman.just run sync
just -f podman.just run check
just -f podman.just run test tests/test_cli_compare.py -q
just -f podman.just run cli compare --help
just -f podman.just                 # default: list the container's project recipes
just -f podman.just preview         # fresh docs build, then preview on port 8000
just -f podman.just preview 8765     # optional host port; stop with Ctrl-C
```

Image build and initial sync need network access. A warm cache doesn't guarantee
offline `check`: fresh-wheel tests and isolated builds may fetch dependencies.
Podman build and run disable automatic proxy-environment forwarding with
`--http-proxy=false`; proxy-dependent contributors must configure networking
deliberately rather than rely on inherited host proxy variables.
The image pins Python 3.14.7 and uv 0.12.9 by image digest and verifies Just 1.58.0
release checksums (amd64/arm64). It also includes checksum-verified Node 24.18.0,
the locked Mermaid CLI, and system Chromium. Do not run `docs-tools` inside the
container: the image already owns the JS tools and browser, and downloading
Puppeteer's Chrome there would leave an unused browser. No external host JS or
browser runtime is needed. Debian apt browser and font packages aren't fully
locked, so these are not bit-identical reproducible images.

Browser sandboxing is enabled by default, including in the container; failures
do not trigger an automatic no-sandbox fallback. If a trusted container build
environment cannot support Chromium's sandbox, explicitly set
`PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX=1` on the host before invoking the Podman
adapter. This container-only opt-in disables the browser sandbox: containers
share the host kernel, so use it only for trusted documentation and dependencies,
not as an isolation guarantee for untrusted content.

On native Linux, use rootless Podman. The writable checkout mount uses
`--userns=keep-id` and SELinux shared relabeling (`:z`), not recursive checkout
chown. Reports, builds, and other outputs written under `/workspace` persist in
the checkout after the disposable container exits. Remote engines need an
explicit engine-visible source path and sharing/ownership setup.

On Windows, start a Linux Podman machine and configure its checkout sharing and
writable ownership first. Set the source to the actual absolute Linux path
visible to that engine, then use the same commands above in PowerShell:

```powershell
# Example only: replace with your provider's actual mounted checkout path.
$env:PERFCHECK_CONTAINER_SOURCE = '/actual/mounted/checkout'
just -f podman.just build
just -f podman.just run sync
just -f podman.just run check
```

`PERFCHECK_CONTAINER_SOURCE` is required on Windows. Its value is provider-specific;
don't blindly translate a `C:\...` path into a Linux path. Native Linux keep-id
and SELinux behavior doesn't apply to Windows/VM sharing. Windows PowerShell 5.1
is intended but untested; the forwarding tests exercise PowerShell 7 on Linux.
Windows script launch uses process-scoped `-ExecutionPolicy Bypass`, not a
machine- or user-level policy change. Organization Group Policy can still block
execution.
Preview publishes only `127.0.0.1:<port>:8000`; Windows desktop reachability through
the Podman machine still needs verification. Ordinary `run` publishes no ports.

The three optional overrides are:

| Variable | Default / purpose |
| --- | --- |
| `PERFCHECK_CONTAINER_IMAGE` | `localhost/perfcheck-dev:py314-uv0129-just1580`, used by both build and run |
| `PERFCHECK_CONTAINER_SOURCE` | Native Linux checkout path; otherwise an engine-visible absolute Linux path, without colons or backslashes |
| `PERFCHECK_CONTAINER_STATE_VOLUME` | `perfcheck-dev-<hash>-py314-v1`, a named volume; `<hash>` is the first 12 hex characters of SHA-256 of the host checkout path |

The volume stores `/container-state/venv` and `/container-state/uv-cache`, isolated
from the host `.venv` and cache. Don't run concurrent sync or mutation state
operations against the same volume. To reset it, stop all users, identify the
exact volume with `podman volume ls`, and remove only that volume, for example
`podman volume rm perfcheck-dev-0123456789ab-py314-v1` after replacing the example
hash with the verified checkout hash. Don't use blanket prune commands. The next
`run sync` recreates the environment; checkout outputs remain separate.

Don't run concurrent host/container writers to the same `docs/_build/`, `dist/`,
`coverage/`, or `mutation/` outputs. Distinct state volumes don't prevent these
shared-checkout output collisions; serialize writers or use separate checkouts.

For the optional mutation pilot, preserve existing `mutation/` evidence as
described below, then run `just -f podman.just run mutation` followed by
`just -f podman.just run sync`. This executes the Unix-only pilot inside Linux,
not native Windows. Container checks likewise verify Linux behavior, not native
Windows compatibility; VM performance isn't directly comparable to native runs.
The adapter preserves arguments up to inner Just; existing shell-recipe quoting
semantics still apply to `test`, `cli`, and other recipes.

Validation so far: focused image-contract/fake-Podman tests passed, along with
host format, lint, and type checks. No Podman engine was available, so real image
builds, container execution, and Windows behavior remain unverified.
Native macOS/Windows rendering and hosted CI likewise remain pending real runs.

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
`mutmut==3.8.1`. This Unix-only manual pilot mutates a disposable snapshot of
`src/perfcheck/regression_aggregation.py`, selecting only
`tests/test_suite_aggregation.py`: one worker, 600-second child budget. It does
not mutate checkout sources or run in ordinary checks; Windows is unsupported.

The central `do_not_mutate_patterns` rule excludes standalone, unqualified
`assert_never(...)` lines in audited exhaustive guards. Native generation also
protects parent-case deletion when it contains an excluded guard; meaningful
sibling status, return and enabled-selection code remains eligible. This changes
the mutation denominator, not the strength or number of application tests.
Coverage exclusions and `mutate_only_covered_lines = false` are unchanged.

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
An all-killed pilot is valid; survivor inspection artifacts exist only when a
survivor is present. Neither exclusion nor survival proves equivalence.

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
