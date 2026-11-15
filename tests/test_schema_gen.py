"""Self-test coverage for the generated policy JSON Schema.

The schema generator asserts that every ``perfcheck.model_types`` ``StrEnum``
emits member *values* (not names) as its JSON Schema ``enum``. These checks
cover that invariant passing on the real enums and failing when a regression
emits names instead.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING

import tools.schema_gen

if TYPE_CHECKING:
    import pytest


class _NamesJsonSchemaAdapter:
    """A stand-in ``TypeAdapter`` that emits member names instead of values."""

    _enum_class: type[enum.StrEnum]

    def __init__(self, enum_class: type[enum.StrEnum]) -> None:
        self._enum_class = enum_class

    def json_schema(self) -> dict[str, object]:
        return {"enum": list(self._enum_class.__members__)}


def test_self_test_passes_for_real_model_enums() -> None:
    # Given: the real ``perfcheck.model_types`` ``StrEnum`` members.
    # When: the schema self-test runs.
    ok = tools.schema_gen.run_self_test()

    # Then: every enum emits member values (not names) as its enum.
    assert ok is True


def test_self_test_catches_names_instead_of_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a model_types ``StrEnum`` whose ``json_schema`` emits member names,
    # not values, and the self-test iterating over just that enum.
    class Color(enum.StrEnum):
        RED = "red"
        GREEN = "green"

    monkeypatch.setattr(
        tools.schema_gen,
        "TypeAdapter",
        _NamesJsonSchemaAdapter,
    )
    monkeypatch.setattr(tools.schema_gen, "_model_types_str_enums", lambda: [Color])

    # When: the schema self-test runs over the injected enum.
    ok = tools.schema_gen.run_self_test()

    # Then: it reports failure because the enum emits names, not values.
    assert ok is False
