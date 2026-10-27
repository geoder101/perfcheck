[unix]
set shell := ["sh", "-cu"]

[windows]
set shell := ["powershell.exe", "-NoLogo", "-Command"]

# List available project commands.
default:
  @just --list

# Run the standard test suite, optionally forwarding pytest arguments.
test *args:
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

# Verify that the committed lockfile resolves without modification.
lock-check:
  uv lock --check

# Provision native documentation rendering tools explicitly (requires Node and npm).
docs-tools:
  npm ci --prefix tools/docs --ignore-scripts
  node tools/docs/node_modules/puppeteer/lib/puppeteer/node/cli.js browsers install chrome

# Build the documentation without cached renderer assets and fail on warnings.
docs-check:
  uv run --group docs sphinx-build -M clean docs docs/_build
  uv run --group docs sphinx-build -M html docs docs/_build -E -a -W

# Preview already-built documentation locally, optionally choosing a port.
docs-preview port="8000": docs-check
  python -m http.server --directory docs/_build/html {{port}}

# Run the standard local verification suite.
check: lock-check format-check lint typecheck test examples-check docs-check build

# Run the optional Unix-only aggregation mutation pilot in isolation.
mutation:
  uv sync --locked --group dev --group docs --group examples --group mutation
  uv run --locked --no-sync python -m tools.mutation_runner

# Verify the lockfile and synchronize ordinary development dependencies.
sync:
  just lock-check
  uv sync --locked --group dev --group docs --group examples
