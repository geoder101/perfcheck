"""Gate decisions for the cache-aware documentation build."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from tools import docs_gate

if TYPE_CHECKING:
    from collections.abc import Sequence

    import pytest

_ROOT: Final = Path(__file__).resolve().parents[1]


def _write_index(directory: Path) -> None:
    _ = (directory / "_build" / "html").mkdir(parents=True, exist_ok=True)
    _ = (directory / "_build" / "html" / "index.html").write_text(
        "<html>", encoding="utf-8"
    )


def _install_key(monkeypatch: pytest.MonkeyPatch, directory: Path, key: str) -> None:
    stored = directory / "stored_key"
    monkeypatch.setattr(docs_gate, "_STORED_KEY", stored)
    _ = (directory / "_build").mkdir(parents=True, exist_ok=True)
    _ = stored.write_text(key, encoding="utf-8")


def _track_build(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    steps: list[str] = []

    def fake_run(command: Sequence[str], *_args: object) -> int:
        tokens = [str(token) for token in command]
        step = "clean" if "-M" in tokens and "clean" in tokens else "html"
        steps.append(step)
        return 0

    monkeypatch.setattr(docs_gate, "_execute_build", fake_run)
    return steps


def test_gate_skips_build_when_inputs_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: the stored hash matches render inputs and the built HTML exists.
    key = "rendered-hash"
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: key)
    monkeypatch.setattr(docs_gate, "_BUILT_INDEX", tmp_path / "index.html")
    _ = (tmp_path / "index.html").write_text("<html>", encoding="utf-8")
    _install_key(monkeypatch, tmp_path, key)
    steps = _track_build(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate"])
    # When: the gate runs without a forced rebuild.
    result = docs_gate.main()
    # Then: no build runs and the gate exits cleanly.
    assert result == 0
    assert steps == []
    assert "docs up to date; skipping rebuild" in capsys.readouterr().out


def test_gate_runs_strict_build_when_inputs_changed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: render inputs changed so nothing is up to date.
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: "changed-hash")
    monkeypatch.setattr(docs_gate, "_STORED_KEY", tmp_path / "stored_key")
    steps = _track_build(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate"])
    # When: the gate runs a rebuild.
    result = docs_gate.main()
    # Then: it cleans then runs the strict build and records the new input hash.
    assert result == 0
    assert steps == ["clean", "html"]
    recorded = (tmp_path / "stored_key").read_text(encoding="utf-8").strip()
    assert recorded == "changed-hash"


def test_gate_forces_build_with_fresh_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an otherwise up-to-date build that a caller forces to rebuild.
    key = "stable-hash"
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: key)
    _write_index(tmp_path)
    _install_key(monkeypatch, tmp_path, key)
    steps = _track_build(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate", "--fresh"])
    # When: the forced rebuild runs despite matching inputs.
    result = docs_gate.main()
    # Then: the strict build runs and the input hash is refreshed.
    assert result == 0
    assert steps == ["clean", "html"]


def test_gate_propagates_strict_build_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a strict build that fails under warnings-as-errors.
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: "changed-hash")
    monkeypatch.setattr(docs_gate, "_STORED_KEY", tmp_path / "stored_key")

    def failing_run(_command: Sequence[str], *_args: object) -> int:
        return 1

    monkeypatch.setattr(docs_gate, "_execute_build", failing_run)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate"])
    # When: the strict build fails.
    result = docs_gate.main()
    # Then: the failure code is returned and the stale hash is not recorded.
    assert result == 1
    assert not (tmp_path / "stored_key").is_file()


def test_is_up_to_date_requires_matching_key_and_built_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a stored key and an isolated built-index path.
    monkeypatch.setattr(docs_gate, "_STORED_KEY", tmp_path / "stored_key")
    index = tmp_path / "index.html"
    monkeypatch.setattr(docs_gate, "_BUILT_INDEX", index)
    _ = (tmp_path / "stored_key").write_text("known", encoding="utf-8")

    # When: the built index is missing, present, or the key does not match.
    without_index = docs_gate.is_up_to_date("known")
    _ = index.write_text("<html>", encoding="utf-8")
    with_index = docs_gate.is_up_to_date("known")
    stale = docs_gate.is_up_to_date("unknown")
    # Then: only the matching key plus an existing index counts as up to date.
    assert without_index is False
    assert with_index is True
    assert stale is False
