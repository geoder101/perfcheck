import json
from typing import TYPE_CHECKING

import pytest
from tools import mutation_evidence
from tools.mutation_runner import prepare_output, snapshot, source_identity

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize("payload", ["{}", "not json", '{"total": 0}'])
def test_invalid_export_is_rejected(tmp_path: Path, payload: str) -> None:
    # Given: an absent inventory or malformed native export.
    export = tmp_path / "stats.json"
    _ = export.write_text(payload)
    # When: the native evidence is parsed.
    with pytest.raises((ValueError, mutation_evidence.EvidenceError)):
        _ = mutation_evidence.read_stats(export)
    # Then: no invalid export is accepted as a successful experiment.


def test_baseline_failure_is_invalid() -> None:
    # Given: a child that exited without completing its clean baseline.
    # When: its status is classified.
    result = mutation_evidence.completion(1, timed_out=False)
    # Then: tool failure is not a successful compatibility result.
    assert result == "invalid"


def test_wall_timeout_is_incomplete() -> None:
    # Given: the wall budget expired.
    # When: its status is classified.
    result = mutation_evidence.completion(-9, timed_out=True)
    # Then: the timeout is reported separately from completed results.
    assert result == "incomplete"


def test_original_checkout_import_is_rejected(tmp_path: Path) -> None:
    # Given: a probe receipt from the original editable tree.
    receipt = tmp_path / "imports.jsonl"
    _ = receipt.write_text(
        json.dumps(
            {
                "module_file": str(tmp_path / "src.py"),
                "nodeid": "tests/test_suite_aggregation.py::test_x",
                "mutant": "x",
                "pid": 1,
            }
        )
        + "\n"
    )
    # When: it is checked against the actual generated tree.
    with pytest.raises(mutation_evidence.EvidenceError):
        _ = mutation_evidence.read_imports(receipt, tmp_path / "mutants")
    # Then: a valid-looking tool exit cannot certify the wrong source import.


def test_empty_inventory_is_rejected(tmp_path: Path) -> None:
    # Given: native stats for an experiment that generated no mutants.
    export = tmp_path / "stats.json"
    _ = export.write_text(
        json.dumps(
            {
                "total": 0,
                "killed": 0,
                "survived": 0,
                "no_tests": 0,
                "skipped": 0,
                "suspicious": 0,
                "timeout": 0,
                "check_was_interrupted_by_user": 0,
                "segfault": 0,
            }
        )
    )
    # When: it is parsed as compatibility evidence.
    with pytest.raises(mutation_evidence.EvidenceError, match="zero"):
        _ = mutation_evidence.read_stats(export)
    # Then: empty success cannot establish tool compatibility.


def test_snapshot_is_independent_of_working_source(tmp_path: Path) -> None:
    # Given: a minimal package and snapshot inputs with stale generated caches.
    root = tmp_path / "working"
    root.mkdir()
    for directory in ("src", "tests", "tools"):
        (root / directory).mkdir()
    source = root / "src/target.py"
    _ = source.write_text("VALUE = 1\n")
    for name in ("pyproject.toml", "uv.lock", "README.md"):
        _ = (root / name).write_text("")
    (root / "mutation").mkdir()
    before = source_identity(root)
    destination = tmp_path / "snapshot"
    # When: the runner snapshots the package and only the copy is mutated.
    snapshot(root, destination)
    _ = (destination / "src/target.py").write_text("VALUE = 2\n")
    # Then: package hashes stay unchanged and generated outputs were not copied.
    assert source_identity(root) == before
    assert not (destination / "mutation").exists()


def test_windows_preflight_is_actionable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Given: the explicitly unsupported Windows execution platform.
    monkeypatch.setattr("tools.mutation_runner.sys.platform", "win32")
    # When: the mutation command preflights its output.
    ready = prepare_output(tmp_path / "mutation")
    # Then: it fails before execution and identifies a supported alternative.
    assert not ready
    assert "Linux/macOS" in capsys.readouterr().err


def test_stale_output_is_not_reused(tmp_path: Path) -> None:
    # Given: a previous experiment receipt.
    _ = (tmp_path / "status.json").write_text("old")
    # When: another experiment targets the same directory.
    ready = prepare_output(tmp_path)
    # Then: old results cannot be accepted or overwritten by a new run.
    assert not ready
    assert (tmp_path / "status.json").read_text() == "old"
