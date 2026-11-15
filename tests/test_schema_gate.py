"""Drift-gate coverage for the committed policy JSON Schema.

The gate regenerates the schema in memory and asserts it is byte-identical to the
committed file. These checks cover a clean file passing and a drifted file
failing. The gate's comparison path is redirected to a temporary copy so the
committed schema is never written or left drifted.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import tools.schema_gate

_COMMITTED_SCHEMA: tuple[str, ...] = ("schemas", "v1", "perfcheck-policy.schema.json")


@pytest.fixture
def schema_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Given: a gate that compares against a temporary copy of the committed
    # schema rather than the checked-out file, so the working tree is never
    # touched (pytest cleans the temporary copy and restores the monkeypatch).
    root = Path(__file__).resolve().parents[1]
    real = root.joinpath(*_COMMITTED_SCHEMA)
    target = tmp_path / "perfcheck-policy.schema.json"
    _ = target.write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(tools.schema_gate, "SCHEMA_REL", (str(target),))
    return target


def test_schema_gate_passes_on_clean_schema(schema_file: Path) -> None:
    # Given: a temporary schema copy identical to the committed file.
    real = Path(__file__).resolve().parents[1].joinpath(*_COMMITTED_SCHEMA)

    # When: the drift gate runs.
    result = tools.schema_gate.main()

    # Then: no drift means the gate passes and the copy matches the committed file.
    assert result == 0
    assert schema_file.read_text(encoding="utf-8") == real.read_text(encoding="utf-8")


def test_schema_gate_fails_on_drifted_schema(
    schema_file: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: a temporary schema copy with appended drift.
    drifted = schema_file.read_text(encoding="utf-8") + "# drift\n"
    _ = schema_file.write_text(drifted, encoding="utf-8")

    # When: the drift gate runs.
    result = tools.schema_gate.main()

    # Then: drift fails the gate and prints a diff to stdout.
    assert result == 1
    output = capsys.readouterr().out
    assert "schema drift" in output
