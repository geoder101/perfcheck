"""Generate the versioned policy JSON Schema from the SuitePolicy model.

This tool is the single source of truth for policy authoring and editor tooling.
It derives a strict, self-describing, versioned JSON Schema from the
``SuitePolicy`` pydantic model and writes it deterministically to
``schemas/v1/perfcheck-policy.schema.json``.

The generated schema is a hosted, versioned public contract, distinct from the
still-unstable internal artifact and Python schemas. ``model_json_schema``
already yields ``additionalProperties: false`` and nested ``$defs``; this tool
adds the draft URI, a stable ``$id``, and a data-level ``$schema`` authoring
aid so editors do not flag it against the strict policy body.

Run from the repository root:

    uv run python -m tools.schema_gen           # regenerate the schema file
    uv run python -m tools.schema_gen --self-test  # assert StrEnum values only
"""

from __future__ import annotations

import argparse
import json
import sys
from enum import StrEnum
from pathlib import Path
from typing import Final

from pydantic import TypeAdapter

from perfcheck import model_types
from perfcheck.policy_models import SuitePolicy

SCHEMA_DRAFT_URI: Final = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID: Final = (
    "https://raw.githubusercontent.com/geoder101/perfcheck/refs/heads/main/"
    "schemas/v1/perfcheck-policy.schema.json"
)
SCHEMA_PATH: Final = (
    Path(__file__).resolve().parents[1]
    / "schemas"
    / "v1"
    / "perfcheck-policy.schema.json"
)
SCHEMA_DESCRIPTION: Final = (
    "Optional authoring aid pointing at the hosted perfcheck policy JSON "
    "Schema; perfcheck strips it before validation and never lets it affect "
    "policy identity or hash."
)


def _model_types_str_enums() -> list[type[StrEnum]]:
    """Return every ``StrEnum`` subclass defined under ``perfcheck.model_types``.

    The base ``StrEnum`` lives in the standard library and ``ArtifactSchemaCode``
    lives under ``perfcheck.errors``, so both are excluded by the module filter.
    """
    target = model_types.__name__
    enums: list[type[StrEnum]] = []

    def visit(cls: type[StrEnum]) -> None:
        for subclass in cls.__subclasses__():
            if subclass.__module__ == target:
                enums.append(subclass)
                visit(subclass)

    visit(StrEnum)
    return enums


def build_schema() -> dict[str, object]:
    """Derive the versioned policy schema from the ``SuitePolicy`` model."""
    schema: dict[str, object] = SuitePolicy.model_json_schema()
    schema["$schema"] = SCHEMA_DRAFT_URI
    schema["$id"] = SCHEMA_ID
    properties = schema["properties"]
    if isinstance(properties, dict):
        properties["$schema"] = {
            "type": "string",
            "format": "uri",
            "description": SCHEMA_DESCRIPTION,
        }
    return schema


def serialize_schema(schema: dict[str, object]) -> str:
    """Serialize with deterministic key order and exactly one trailing newline."""
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def run_self_test() -> bool:
    """Assert every ``model_types`` ``StrEnum`` emits member values as enum."""
    ok = True
    for enum_class in _model_types_str_enums():
        enum_schema: dict[str, object] = TypeAdapter(enum_class).json_schema()
        emitted = enum_schema.get("enum")
        expected = [member.value for member in enum_class]
        if emitted != expected:
            ok = False
            detail = (
                f"self-test failed: {enum_class.__name__}: "
                f"{emitted!r} != {expected!r}\n"
            )
            _ = sys.stderr.write(detail)
    return ok


def main(argv: list[str] | None = None) -> int:
    """Run the embedded self-test, then regenerate the schema file."""
    parser = argparse.ArgumentParser(description=__doc__)
    _ = parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run the embedded StrEnum self-test and exit without writing.",
    )
    args = parser.parse_args(argv)
    if not run_self_test():
        return 1
    if getattr(args, "self_test", False):
        return 0
    text = serialize_schema(build_schema())
    SCHEMA_PATH.parent.mkdir(parents=True, exist_ok=True)
    _ = SCHEMA_PATH.write_text(text, encoding="utf-8")
    _ = sys.stdout.write(f"wrote {SCHEMA_PATH}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
