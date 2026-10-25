from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final, Literal

import pytest
from pydantic import JsonValue, TypeAdapter
from tools.quality_evidence import app
from typer.testing import CliRunner

_ROOT: Final = Path(__file__).parents[1]
_JSON: Final = TypeAdapter(dict[str, JsonValue])
_CLI: Final = CliRunner()


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    git = shutil.which("git")
    assert git
    root = tmp_path / "checkout"
    _ = subprocess.run(  # noqa: S603 - local disposable Git fixture only.
        [git, "clone", "--quiet", "--no-hardlinks", str(_ROOT), str(root)],
        env={**os.environ, "GIT_MASTER": "1"},
        check=True,
        capture_output=True,
        timeout=30,
    )
    monkeypatch.chdir(root)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(tmp_path / "summary"))
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "output"))
    assert _CLI.invoke(app, ["prepare"]).exit_code == 0
    _ = (root / "sample.py").write_text("x = 1\nif x:\n    x = 2\n")
    for arguments in (
        ("run", "--branch", "sample.py"),
        ("json", "-o", "coverage/coverage.json"),
        ("html", "-d", "coverage/html"),
    ):
        _ = subprocess.run(  # noqa: S603 - real coverage on the disposable sample.
            [sys.executable, "-m", "coverage", *arguments],
            cwd=root,
            env={
                **{
                    k: v
                    for k, v in os.environ.items()
                    if not k.startswith(("COVERAGE_", "COV_CORE_", "_COVERAGE_"))
                },
                "COVERAGE_RCFILE": os.devnull,
                "COVERAGE_FILE": str(root / "coverage/.coverage"),
            },
            check=True,
            capture_output=True,
            timeout=30,
        )
    return root


@pytest.mark.parametrize("damage", ["branches", "html", "asset"])
def test_incoherent_reports_are_not_published(
    project: Path, damage: Literal["branches", "html", "asset"]
) -> None:
    # Given: fresh files disagree with raw branch execution or lack usable HTML.
    if damage == "branches":
        path = project / "coverage/coverage.json"
        _ = path.write_text(
            path.read_text()
            .replace('"covered_branches": 1', '"covered_branches": 2')
            .replace('"missing_branches": 1', '"missing_branches": 0')
            .replace('"percent_covered": 80.0', '"percent_covered": 100.0')
        )
    if damage == "html":
        _ = (project / "coverage/html/index.html").write_text("not HTML")
    if damage == "asset":
        next((project / "coverage/html").glob("*.css")).unlink()
    # When: the real exporter validates the result set.
    result = _CLI.invoke(app, ["export", "--outcome", "success"])
    # Then: inconsistent artifacts cannot be called complete or staged.
    assert result.exit_code != 0
    metadata = _JSON.validate_json(
        (project / "coverage/evidence/provenance.json").read_bytes()
    )
    assert metadata["availability"] == "unavailable"
    assert not (project / "coverage/evidence/.coverage").exists()


def test_failed_gate_reports_are_partial_not_complete(project: Path) -> None:
    # Given: fresh reports may exist after an early collection or interrupted run.
    # When: only the actual failed step outcome is known.
    result = _CLI.invoke(app, ["export", "--outcome", "failure"])
    # Then: no full-suite completion is claimed, but diagnostic reports survive.
    assert result.exit_code == 1
    metadata = _JSON.validate_json(
        (project / "coverage/evidence/provenance.json").read_bytes()
    )
    assert metadata["availability"] == "partial"
    assert (project / "coverage/evidence/.coverage").is_file()


def test_actual_changed_head_preserves_measurement_revision(project: Path) -> None:
    # Given: Git HEAD changes after preparation and measurement in a sandbox.
    marker = _JSON.validate_json(
        (project / "coverage/evidence/start.json").read_bytes()
    )
    git = shutil.which("git")
    assert git
    _ = subprocess.run(  # noqa: S603 - disposable checkout, no new commits.
        [git, "checkout", "--quiet", "--detach", "HEAD~1"],
        env={**os.environ, "GIT_MASTER": "1"},
        check=True,
        timeout=10,
    )
    # When: export detects the actual changed HEAD.
    result = _CLI.invoke(app, ["export", "--outcome", "success"])
    # Then: the later revision is not falsely labeled tested.
    assert result.exit_code == 1
    metadata = _JSON.validate_json(
        (project / "coverage/evidence/provenance.json").read_bytes()
    )
    assert metadata["tested_sha"] == marker["tested_sha"]
    assert metadata["observed_export_sha"] != metadata["tested_sha"]


@pytest.mark.parametrize("target", [".coverage", "html"])
def test_rejected_staging_links_cannot_enable_upload(
    project: Path, tmp_path: Path, target: str
) -> None:
    # Given: rejected staging paths point outside the explicit evidence allowlist.
    destination = tmp_path / "outside"
    destination.mkdir()
    secret = destination / "keep"
    _ = secret.write_text("must not upload")
    path = project / "coverage/evidence" / target
    try:
        path.symlink_to(
            destination if target == "html" else secret,
            target_is_directory=target == "html",
        )
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")
    # When: export rejects the unsafe tree before publication.
    result = _CLI.invoke(app, ["export", "--outcome", "success"])
    # Then: upload readiness fails closed even if rejected files remain present.
    assert result.exit_code != 0
    output = (tmp_path / "output").read_text()
    assert "publish=false" in output
    assert "publish=true" not in output
    assert secret.read_text() == "must not upload"
