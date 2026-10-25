from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from tools.mutation_ci_artifacts import ci_directory, stage
from tools.mutation_summary import export

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.skipif(sys.platform == "win32", reason="Unix symlink control")
def test_rejected_receipt_retains_safe_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: redirected status beside safe public stdout and failure logs.
    root, ci = tmp_path / "checkout", tmp_path / "runner-temp/mutation-ci"
    (root / "mutation").mkdir(parents=True)
    ci.mkdir(parents=True)
    secret = tmp_path / "private"
    _ = secret.write_text("must never be copied")
    (root / "mutation/status.json").symlink_to(secret)
    _ = (root / "mutation/baseline.log").write_text("baseline failed\n")
    _ = (ci / "stdout.log").write_text("pilot failed\n")
    monkeypatch.setenv("RUNNER_TEMP", str(ci.parent))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary.md"))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "outputs"))
    # When: the actual exporter's artifact-staging boundary runs.
    result = export(root)
    # Then: unsafe evidence rejects completion without discarding safe diagnostics.
    assert result == 1
    assert (tmp_path / "outputs").read_text() == "publish=true\n"
    assert "Evidence rejected or unavailable" in (tmp_path / "summary.md").read_text()
    evidence = ci / "evidence"
    assert (evidence / "mutation/baseline.log").read_text() == "baseline failed\n"
    assert (evidence / "mutation-ci/stdout.log").read_text() == "pilot failed\n"
    assert not (evidence / "mutation/status.json").exists()


def test_native_spans_are_selected_but_unknown_files_are_excluded(
    tmp_path: Path,
) -> None:
    # Given: known native target spans and an unrelated workspace file.
    root, ci = tmp_path / "checkout", tmp_path / "runner-temp/mutation-ci"
    target = root / "mutation/mutants/src/perfcheck/regression_aggregation.py.spans"
    target.parent.mkdir(parents=True)
    ci.mkdir(parents=True)
    _ = target.write_text("native spans\n")
    _ = (root / "mutation/unapproved.log").write_text("not selected\n")
    # When: the actual exporter allowlist is staged.
    accepted = stage(root, ci)
    # Then: native diagnostics are retained without copying arbitrary files.
    assert accepted
    assert (ci / "evidence" / target.relative_to(root)).read_text() == "native spans\n"
    assert not (ci / "evidence/mutation/unapproved.log").exists()


def test_ci_output_is_under_runner_temp_not_the_checkout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: GitHub provides a runner-owned temporary directory.
    temporary = tmp_path / "runner-temp"
    monkeypatch.setenv("RUNNER_TEMP", str(temporary))
    # When: CI-only evidence storage is resolved.
    directory = ci_directory()
    # Then: no new generated-output ignore rule is needed in the checkout.
    assert directory == temporary / "mutation-ci"
