"""Gate decisions for the cache-aware documentation build."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

import pytest
from tools import docs_gate

if TYPE_CHECKING:
    from collections.abc import Sequence

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


def test_is_up_to_date_missing_key_never_reports_up_to_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: no stored input hash exists yet (fresh checkout or empty cache).
    monkeypatch.setattr(docs_gate, "_STORED_KEY", tmp_path / "missing")
    monkeypatch.setattr(docs_gate, "_BUILT_INDEX", tmp_path / "index.html")
    # When: any key is compared against the absent stored hash.
    result = docs_gate.is_up_to_date("known")
    # Then: a missing stored key can never match, so no rebuild is skipped.
    assert result is False


def test_gate_propagates_html_step_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: the clean step succeeds but the strict HTML build fails on warnings.
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: "changed-hash")
    monkeypatch.setattr(docs_gate, "_STORED_KEY", tmp_path / "stored_key")

    def html_run(command: Sequence[str], *_args: object) -> int:
        tokens = [str(token) for token in command]
        return 1 if "html" in tokens else 0

    monkeypatch.setattr(docs_gate, "_execute_build", html_run)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate"])
    # When: the HTML render fails after a successful clean.
    result = docs_gate.main()
    # Then: the failure code is returned and the stale hash is not recorded.
    assert result == 1
    assert not (tmp_path / "stored_key").is_file()


def test_gate_forces_build_with_fresh_flag_when_index_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an up-to-date stored hash but no built HTML, forced to rebuild.
    key = "stable-hash"
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: key)
    _install_key(monkeypatch, tmp_path, key)
    steps = _track_build(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate", "--fresh"])
    # When: the forced rebuild runs despite a missing output index.
    result = docs_gate.main()
    # Then: it still cleans then builds and refreshes the input hash.
    assert result == 0
    assert steps == ["clean", "html"]
    recorded = (tmp_path / "stored_key").read_text(encoding="utf-8").strip()
    assert recorded == key


@pytest.mark.parametrize("failed_step", ["clean", "html"])
def test_failed_forced_build_cannot_reuse_old_html(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failed_step: str
) -> None:
    # Given: matching cached inputs and old HTML that survives a failed rebuild.
    key = "stable-hash"
    monkeypatch.setattr(docs_gate, "docs_input_sha", lambda: key)
    index = tmp_path / "index.html"
    _ = index.write_text("old HTML", encoding="utf-8")
    monkeypatch.setattr(docs_gate, "_BUILT_INDEX", index)
    _install_key(monkeypatch, tmp_path, key)

    def fail(command: Sequence[str], *_args: object) -> int:
        return 1 if failed_step in command else 0

    monkeypatch.setattr(docs_gate, "_execute_build", fail)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate", "--fresh"])

    # When: a forced build fails, then an ordinary invocation retries.
    failed = docs_gate.main()
    steps = _track_build(monkeypatch)
    monkeypatch.setattr(sys, "argv", ["tools.docs_gate"])
    retried = docs_gate.main()

    # Then: retained HTML does not count as a successful build.
    assert failed == 1
    assert retried == 0
    assert steps == ["clean", "html"]
