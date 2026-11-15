[unix]
set shell := ["sh", "-cu"]

[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

# List available project commands.
default:
  @just --list

# Run the standard test suite in parallel with a per-test timeout safety net.
test *args:
  uv run pytest -n auto --ignore=tests/test_examples.py --ignore=tests/test_examples_check.py {{args}}

# Run the standard test suite serially, optionally forwarding pytest arguments.
test-serial *args:
  uv run pytest --ignore=tests/test_examples.py --ignore=tests/test_examples_check.py {{args}}

# Measure application statement and branch coverage with the standard test selection.
[env("COVERAGE_RCFILE", justfile_directory() / "pyproject.toml")]
[env("COVERAGE_FILE", justfile_directory() / "coverage/.coverage")]
coverage *args:
  uv run pytest --ignore=tests/test_examples.py --ignore=tests/test_examples_check.py --cov --cov-config="{{justfile_directory() / 'pyproject.toml'}}" --cov-report=term-missing --cov-report=html --cov-report=json {{args}}

# Enforce fresh full-suite combined statement and branch coverage at 99%.
coverage-check:
  uv run python -m tools.coverage_gate

# Validate the optional Marimo curriculum and its focused test modules.
examples-check:
  uv run --group examples python -m tests.examples_check

# Run one notebook as a Marimo app.
[unix]
notebook-run $notebook:
  uv run --group examples marimo run "$notebook"

# Run one notebook as a Marimo app.
[windows]
notebook-run $notebook:
  uv run --group examples marimo run "$env:notebook"; exit $LASTEXITCODE

# Edit one notebook in Marimo.
[unix]
notebook-edit $notebook:
  uv run --group examples marimo edit "$notebook"

# Edit one notebook in Marimo.
[windows]
notebook-edit $notebook:
  uv run --group examples marimo edit "$env:notebook"; exit $LASTEXITCODE

# Execute one notebook as a Python script.
[unix]
notebook-script $notebook:
  uv --directory . run --group examples python "$notebook"

# Execute one notebook as a Python script.
[windows]
notebook-script $notebook:
  uv --directory . run --group examples python "$env:notebook"; exit $LASTEXITCODE

# Run the perfcheck CLI, optionally forwarding CLI arguments.
cli *args:
  uv run perfcheck {{args}}

# Check Python formatting without changing files.
format-check:
  uv run ruff format --check .

# Apply the project's Python formatter.
format:
  uv run ruff format .

# Run lint checks.
lint:
  uv run ruff check .

# Run strict static type checking.
typecheck:
  uv run basedpyright

# Build source and wheel distributions.
build:
  uv build --no-sources

# Install the tool locally into a managed uv tool environment (exposes `perfcheck` on PATH).
install:
  uv tool install .

# Verify that the committed lockfile resolves without modification.
lock-check:
  uv lock --check

# Provision native documentation rendering tools explicitly (requires Node and npm).
docs-tools:
  npm ci --prefix tools/docs --ignore-scripts
  node tools/docs/node_modules/puppeteer/lib/puppeteer/node/cli.js browsers install chrome

# Build the documentation only when render inputs changed, failing on warnings.
# Pass --fresh to force a rebuild regardless of the cached input hash.
docs-check *args:
  uv run python -m tools.docs_gate {{args}}

# Preview already-built documentation locally, optionally choosing a port.
docs-preview port="8000": docs-check
  python -m http.server --directory docs/_build/html {{port}}

# Clear the content-addressed cache that lets the docs render tests reuse a build.
docs-cache-clear:
  rm -rf .pytest_docs_cache .docs_inputs_sha

# Regenerate the hosted versioned policy JSON Schema deterministically.
schema-gen:
  uv run python -m tools.schema_gen

# Verify the committed policy JSON Schema regenerates byte-identically (drift gate).
schema-check:
  uv run python -m tools.schema_gate

# Run the standard local verification suite.
check: lock-check schema-check format-check lint typecheck test examples-check docs-check build

# Run the optional Unix-only aggregation mutation pilot in isolation.
mutation:
  uv sync --locked --group dev --group docs --group examples --group mutation
  uv run --locked --no-sync python -m tools.mutation_runner

# Verify the lockfile and synchronize ordinary development dependencies.
sync:
  just lock-check
  uv sync --locked --group dev --group docs --group examples

# Upgrade all packages to the latest compatible versions, then sync dev, docs, and examples.
upgrade-deps:
  just lock-check
  uv lock --upgrade --refresh
  uv sync --locked --group dev --group docs --group examples
