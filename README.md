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
  writes JSON and Markdown reports.

## Quality checks

Run the same local checks before contributing documentation or code:

```bash
uv run pytest
uv run ruff check .
uv run basedpyright
```

## Scope

Internal implementation may change or be removed during breaking cleanup; this
README does not promise compatibility or stability for internal APIs or artifact
schemas. The supported surface described here is limited to the current CLI
commands. No dashboard, database, DSL, HTML, or other external integrations are
promised.
