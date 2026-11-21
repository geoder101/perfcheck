# perfcheck

`perfcheck` provides reproducible performance-regression evidence for CI.

## Install

For a native checkout, install Python 3.14 or later,
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

Start with the [Project documentation](https://geoder101.github.io/perfcheck/index.html)
for a workflow overview and four [Diataxis-style](https://diataxis.fr/) paths:
Tutorials, How-to guides, Reference, and Explanation.
The [Marimo curriculum index](examples/README.md) offers eleven executable lessons
in order, from the CLI workflow to statistical mechanics and comparative methods.
Choose a beginner, practitioner, or deep-dive route in
[Learning paths](https://geoder101.github.io/perfcheck/explanation/learning-paths.html).
The routes connect the
probability, experimental-design, inference/power, and multiple-testing chapters
to interactive labs 06–10 and the lesson 05 CLI capstone. The
[performance verification case study](https://geoder101.github.io/perfcheck/tutorials/performance-verification-case-study.html)
walks through actual artifacts and CI outcomes; teaching methods don't add
production decision engines.

The Furo documentation site is optional; it is not needed to run the CLI.
Build it or preview it locally from the repository root:

```bash
just docs-tools          # explicit native provisioning; requires Node 24.18.0 and npm
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
just cli policy --help
just cli collect --help
just cli summarize --help
just cli compare --help
```

- `policy` groups the authoring helpers: `policy check` validates a policy
  parses and its content hash matches; `policy stamp` rewrites canonical JSON
  stamped with the correct hash. Use them before collecting, summarizing, or
  comparing to fail fast on a malformed policy.
- `collect` writes one raw run artifact from all metrics in a suite.
- `summarize` writes one canonical summary artifact from a verified raw run.
- `compare` evaluates current and baseline summaries (or raw-run inputs) and
  writes JSON (`--report-json`), Markdown (`--report-md`), or both. At least
  one report output is required; `--json` additionally emits JSON to stdout.

## Prometheus authentication

`collect` authenticates to Prometheus with four optional flags, resolved from
the flag with the matching environment variable as fallback and a flag winning
over its env var. No policy is involved.

| Flag                               | Purpose                                                                |
| ---------------------------------- | ---------------------------------------------------------------------- |
| `--prometheus-auth-scheme`         | Scheme: `none`, `bearer`, or `basic`. The CLI rejects any other value. |
| `--prometheus-bearer-token`        | Bearer token, matched by `PERFCHECK_PROMETHEUS_BEARER_TOKEN`.          |
| `--prometheus-auth-basic-user`     | Basic username, matched by `PERFCHECK_PROMETHEUS_BASIC_USERNAME`.      |
| `--prometheus-auth-basic-password` | Basic password, matched by `PERFCHECK_PROMETHEUS_BASIC_PASSWORD`.      |

`none` sends no `Authorization` header, `bearer` sends `Authorization: Bearer
<token>`, and `basic` sends `Authorization: Basic <base64(user:pass)>`, encoding
the username and password as UTF-8 before Base64 encoding. Setting
only `PERFCHECK_PROMETHEUS_BEARER_TOKEN` still infers bearer auth. The resolved
scheme and header are forwarded to the transport only; the token and password
never reach the artifact, labels, provenance, logs, or CLI output. An
incomplete configuration (for example, `basic` with no password) fails with a
secret-free message and exit status `3`.

See the how-to guide [Authenticate Prometheus collection](https://geoder101.github.io/perfcheck/how-to/prometheus-authentication.html)
for a step-by-step walkthrough.

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
just -f podman.just              # default: list the container's project recipes
just -f podman.just preview      # fresh docs build, then preview on port 8000
just -f podman.just preview 8765 # optional host port; stop with Ctrl-C
```

Image build and initial sync need network access. A warm cache doesn't guarantee
offline `check`: fresh-wheel tests and isolated builds may fetch dependencies.
Podman build and run disable automatic proxy-environment forwarding with
`--http-proxy=false`; proxy-dependent contributors must configure networking
deliberately rather than rely on inherited host proxy variables.
The image pins Python 3.14.10 and uv 0.12.24 by image digest and verifies Just 1.59.0
release checksums (amd64/arm64). It also includes checksum-verified Node 24.18.1,
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
and 7 are supported; the forwarding tests exercise PowerShell 7 on Linux.
Windows script launch uses process-scoped `-ExecutionPolicy Bypass`, not a
machine- or user-level policy change. Organization Group Policy can still block
execution.
Preview publishes only `127.0.0.1:<port>:8000`. Ordinary `run` publishes no ports.

The three optional overrides are:

| Variable                           | Default / purpose                                                                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `PERFCHECK_CONTAINER_IMAGE`        | `localhost/perfcheck-dev:py314-uv0129-just1580`, used by both build and run                                                   |
| `PERFCHECK_CONTAINER_SOURCE`       | Native Linux checkout path; otherwise an engine-visible absolute Linux path, without colons or backslashes                    |
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

Validation: focused image-contract/fake-Podman tests pass, along with host format,
lint, and type checks. CI runs the fast Linux gate on every push and the full check
once a merge reaches the default branch.

### Coverage evidence

Coverage is opt-in:

```bash
just coverage
just coverage tests/test_cli_compare.py # optional pytest selection/arguments
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

### Upgrading dependencies

Upgrade the runtime dependencies and every `uv` group (`dev`, `docs`, `examples`,
and the optional `mutation` group), and review the `uv_build` build backend
separately. Keep the declared Python range `>=3.14,<3.15` unchanged; the `uv`
executable, npm tooling, OS packages, and container images are separate tasks.

Prepare the checkout, preserving other work, and record known baseline check failures
to tell them apart from upgrade-induced ones. Review `pyproject.toml` and update pins
in this order, choosing stable compatible candidates (from official PyPI metadata or
upstream listings, not prereleases or the newest version), and checking anything
affecting CLI behavior, numerical results, validation, lint/type rules, documentation,
and the executable lessons:

1. Update exact pins and upper bounds in `[project].dependencies` and every
   `[dependency-groups]` entry where a reviewed candidate requires it; retain justified
   compatibility limits and the mutation group's Windows exclusion marker.
2. Review `[build-system].requires` separately and update its `uv_build` constraint
   when appropriate; isolated build requirements aren't necessarily in `uv.lock`.

Refresh the lockfile within the declared constraints — a maintenance exception,
because no Just recipe covers upgrades:

```bash
uv lock --upgrade
```

It reconsiders locked versions without bypassing pins, upper bounds, or compatibility
rules, and resolution includes groups that aren't installed in the ordinary
environment. Review the `pyproject.toml`/`uv.lock` diff for direct and transitive
changes, artifact hashes, sources, and group membership, keep credentials out of
persisted files and diagnostics, and investigate a held-back transitive dependency's
parent constraint rather than forcing an incompatible version.

Install the locked groups and check:

```bash
just sync
```

This verifies the lockfile and installs the locked runtime plus `dev`/`docs`/`examples`
groups, excluding optional mutation tooling; don't treat resolution or installation as
proof of compatibility. On a supported Unix platform, also check the optional group,
whose `mutmut` requirement excludes Windows:

```bash
uv sync --locked --group dev --group docs --group examples --group mutation
uv run --locked --no-sync python -c "from importlib.metadata import version; import mutmut; print(version('mutmut'))"
just sync
```

Leave existing `mutation/` evidence untouched, don't start `just mutation` merely to
validate an upgrade, and always run the final `just sync` separately to restore the
ordinary environment, even if the optional install or probe fails.

Run the complete quality gate:

```bash
just check
```

This runs lock verification, formatting, lint, strict type checking, tests,
executable examples, strict documentation, and source/wheel builds; the final
`just build` stage checks the separately declared build backend. Ordinary checks
remain coverage-free and mutation-free. Decide for each failure whether the dependency
change introduced it or whether it was already in the baseline, make scoped
compatibility fixes, and add behavior regression tests when behavior changes; don't add
version-only snapshots or suppress errors to make checks green.

## Scope

Internal implementation may change or be removed during breaking cleanup; this
README does not promise compatibility or stability for internal APIs or artifact
schemas. The supported surface described here is limited to the current CLI
commands. No dashboard, database, DSL, HTML, or other external integrations are
promised.

The generated JSON Schema at `schemas/v1/perfcheck-policy.schema.json` is a
hosted, versioned public contract for the policy file, not a Python-API
compatibility promise. It is pinned to a single major version and served raw
from the default branch; versioned schema files are immutable and are never
overwritten in place.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
