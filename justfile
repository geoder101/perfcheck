set shell := ["bash", "-cu"]

# List available project commands.
default:
  @just --list

# Run the complete test suite, optionally forwarding pytest arguments.
test *args:
  uv run pytest {{args}}

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

# Run the standard local verification suite.
check: format-check lint typecheck test

# Verify the lockfile and synchronize all development dependencies.
sync:
  uv lock --check
  uv sync --locked --all-groups
