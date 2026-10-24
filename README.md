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
just check
```

Coverage is opt-in and does not change `just test` or `just check`:

```bash
just coverage
just coverage tests/test_cli_compare.py   # optional pytest selection/arguments
```

This measures statements and branches in `src/perfcheck` using the same test
selection as `just test`, including instrumentable Python subprocesses. Open
`coverage/html/index.html` or inspect `coverage/coverage.json`; combined raw data
is retained at `coverage/.coverage`. These generated outputs are ignored and replaced on
each run. There is no coverage threshold. Coverage records execution, not the
strength of assertions. The optional curriculum remains a separate
`just examples-check` gate, outside this baseline. Fresh-wheel smoke tests still
run in clean application-only environments: they verify packaging functionality
but their installed-wheel execution is not claimed as instrumented coverage.

## Scope

Internal implementation may change or be removed during breaking cleanup; this
README does not promise compatibility or stability for internal APIs or artifact
schemas. The supported surface described here is limited to the current CLI
commands. No dashboard, database, DSL, HTML, or other external integrations are
promised.
