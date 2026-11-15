"""Drift-only gate: assert the committed policy schema regenerates byte-identically.

This gate regenerates the versioned policy JSON Schema in-memory from the
``SuitePolicy`` model via ``tools.schema_gen`` and compares the deterministic
bytes to the committed file at ``schemas/v1/perfcheck-policy.schema.json``. It
never writes or modifies the committed file; it only fails on drift.

Run from the repository root:

    uv run python -m tools.schema_gate
"""

from __future__ import annotations

import sys
from difflib import unified_diff
from pathlib import Path
from typing import Final

from tools.schema_gen import build_schema, serialize_schema

SCHEMA_REL: Final = ("schemas", "v1", "perfcheck-policy.schema.json")


def _unified_diff(expected: str, actual: str) -> str:
    """Return a minimal unified-style diff of two serialized schemas."""
    return "".join(
        unified_diff(
            expected.splitlines(keepends=True),
            actual.splitlines(keepends=True),
            fromfile="committed",
            tofile="regenerated",
            n=1,
        )
    )


def main() -> int:
    """Fail on any drift between the committed schema and a fresh regeneration."""
    root = Path(__file__).resolve().parents[1]
    committed = root.joinpath(*SCHEMA_REL)
    try:
        expected = committed.read_text(encoding="utf-8")
    except OSError as error:
        _ = sys.stderr.write(f"cannot read committed schema {committed}: {error}\n")
        return 1
    actual = serialize_schema(build_schema())
    if expected == actual:
        return 0
    _ = sys.stdout.write(
        "schema drift: committed schema is not byte-identical to a fresh regeneration\n"
    )
    _ = sys.stdout.write(f"expected (committed): {committed}\n")
    _ = sys.stdout.write(f"actual   (regenerated): {committed}\n")
    _ = sys.stdout.write(_unified_diff(expected, actual))
    return 1


if __name__ == "__main__":
    sys.exit(main())
