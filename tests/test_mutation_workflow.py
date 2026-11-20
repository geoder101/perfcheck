from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final, Literal, assert_never

import pytest
from tools.mutation_ci_models import Manifest, Start, Status
from tools.mutation_evidence import NativeStats

type Failure = Literal[
    "baseline",
    "timeout",
    "malformed",
    "missing",
    "mismatch",
    "counts",
    "sha",
    "report",
    "symlink",
]

_ROOT: Final = Path(__file__).parents[1]
_WORKFLOW: Final = _ROOT / ".github/workflows/mutation.yml"
_TARGET: Final = "src/perfcheck/regression_aggregation.py"
_GIT: Final = shutil.which("git") or "git"


def command(root: Path, mode: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed module and internal phase arguments
        [sys.executable, "-m", "tools.mutation_summary", mode],
        cwd=root,
        env={**os.environ, "PYTHONPATH": str(_ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


@pytest.fixture
def campaign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path
    (root / "src/perfcheck").mkdir(parents=True)
    _ = (root / _TARGET).write_text("VALUE = 1\n")
    _ = (root / "uv.lock").write_text("locked\n")
    for args in (
        ("init",),
        ("add", "."),
        (
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-m",
            "fixture",
        ),
    ):
        _ = subprocess.run(  # noqa: S603 - fixed local fixture commands
            [_GIT, *args],
            cwd=root,
            check=True,
            capture_output=True,
        )
    sha = subprocess.check_output(  # noqa: S603 - fixed Git identity command
        [_GIT, "rev-parse", "HEAD"], cwd=root, text=True
    ).strip()
    monkeypatch.setenv("GITHUB_SHA", sha)
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_dispatch")
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("RUNNER_TEMP", str(root))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(root / "summary.md"))
    monkeypatch.setenv("GITHUB_OUTPUT", str(root / "outputs"))
    monkeypatch.setenv("MUTATION_OUTCOME", "success")
    prepared = command(root, "prepare")
    assert prepared.returncode == 0, prepared.stderr
    output = root / "mutation"
    (output / "mutants/src/perfcheck").mkdir(parents=True)
    receipt = Start.model_validate_json((root / "mutation-ci/start.json").read_text())
    manifest = Manifest(
        target=_TARGET,
        tests="tests/test_suite_aggregation.py",
        source_sha256=receipt.source_sha256,
        lock_sha256=receipt.lock_sha256,
        workers=1,
        child_budget_seconds=600,
    )
    _ = (output / "manifest.json").write_text(manifest.model_dump_json())
    status = Status(
        status="complete",
        detail="validated",
        elapsed_seconds=2.0,
        source_unchanged=True,
    )
    _ = (output / "status.json").write_text(status.model_dump_json())
    stats = NativeStats(
        killed=1,
        survived=1,
        total=2,
        no_tests=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        check_was_interrupted_by_user=0,
        segfault=0,
    )
    _ = (output / "mutants/mutmut-cicd-stats.json").write_text(stats.model_dump_json())
    keys = {f"perfcheck.regression_aggregation.mutmut_{i}": i for i in (0, 1)}
    _ = (output / f"mutants/{_TARGET}.meta").write_text(
        json.dumps(
            {
                "exit_code_by_key": keys,
                "hash_by_function_name": {},
                "type_check_error_by_key": {},
                "durations_by_key": {},
                "estimated_durations_by_key": {},
            }
        )
    )
    for name in (
        "results.txt",
        "run.log",
        "baseline.log",
        "parse.log",
        "outcomes.json",
        "inspection.json",
        "imports.jsonl",
        "inspection-imports.jsonl",
        "forced-failure.log",
        "generated-baseline.log",
        "export.log",
    ):
        _ = (output / name).write_text(
            "" if name == "parse.log" else "fixture evidence\n"
        )
    return root


def test_workflow_is_manual_bounded_and_read_only() -> None:
    # Given: the actual workflow, not a separate policy fixture.
    # When: its executable controls are inspected.
    workflow = _WORKFLOW.read_text()
    # Then: the manual experiment cannot become a privileged or required gate.
    assert "on:\n  workflow_dispatch:\n" in workflow
    assert "permissions:\n  contents: read\n" in workflow
    assert "runs-on: ubuntu-latest" in workflow
    assert "timeout-minutes: 15" in workflow
    assert 'python-version: "3.14"' in workflow
    assert 'just-version: "1.58.0"' in workflow
    assert "ref: ${{ github.sha }}" in workflow
    assert "persist-credentials: false" in workflow
    assert (
        "uv sync --locked --group dev --group docs --group examples --group mutation"
        in workflow
    )
    assert 'just mutation 2>&1 | tee "$RUNNER_TEMP/mutation-ci/stdout.log"' in workflow
    assert "set -o pipefail" in workflow
    assert "MUTATION_OUTCOME: ${{ steps.pilot.outcome }}" in workflow
    assert (
        "uv run --locked --no-sync python -m tools.mutation_summary export" in workflow
    )
    assert "if: always()" in workflow
    assert "steps.evidence.outputs.publish == 'true'" in workflow
    assert "retention-days: 7" in workflow
    assert "${{ runner.temp }}/mutation-ci/evidence/" in workflow
    assert all(
        word not in workflow
        for word in (
            "continue-on-error",
            "secrets.",
            "schedule:",
            "pull_request",
            "pages:",
            "actions/cache",
            "contents: write",
            "--all-groups",
        )
    )


def test_action_sha_pins_match_verified_official_releases() -> None:
    # Given: live-verified immutable commit SHAs and their release tags.
    expected_sha = {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "astral-sh/setup-uv": "1db35dd8eee11c5894872e0b383ae6c406cf738d",
        "extractions/setup-just": "53165ef7e734c5c07cb06b3c8e7b647c5aa16db3",
        "actions/upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    }
    expected_tag = {
        "actions/checkout": "v7.0.1",
        "astral-sh/setup-uv": "v10.4.0",
        "extractions/setup-just": "v4.0.0",
        "actions/upload-artifact": "v7.0.2",
    }
    # When: actual workflow action references (tagged with their release) are parsed.
    compiled = re.compile(r"uses: ([^@\s]+)@([0-9a-f]{40})(?:\s+#\s+(\S+))?")
    parsed = {
        match.group(1): (match.group(2), match.group(3))
        for match in compiled.finditer(_WORKFLOW.read_text())
    }
    # Then: only the exact verified SHAs execute, each remembered with its release tag.
    assert parsed == {
        action: (expected_sha[action], expected_tag[action]) for action in expected_sha
    }


def test_survivors_are_advisory_with_actual_checkout_receipt(campaign: Path) -> None:
    # Given: a complete pilot containing a surviving mutant.
    # When: the workflow's summary entry point exports evidence.
    result = command(campaign, "export")
    # Then: survivors do not fail the pilot; exact source identity is downloadable.
    assert result.returncode == 0, result.stderr
    summary = (campaign / "summary.md").read_text()
    assert "Status: complete" in summary
    assert "survived: 1" in summary
    assert "advisory" in summary
    assert (campaign / "mutation-ci/evidence/mutation-ci/start.json").is_file()
    assert "publish=true" in (campaign / "outputs").read_text()


@pytest.mark.parametrize(
    "failure",
    [
        "baseline",
        "timeout",
        "malformed",
        "missing",
        "mismatch",
        "counts",
        "sha",
        "report",
        "symlink",
    ],
)
def test_invalid_or_unavailable_evidence_fails_honestly(
    campaign: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: Failure,
) -> None:
    # Given: a controlled invalid, interrupted, missing or contradictory receipt.
    status = campaign / "mutation/status.json"
    match failure:
        case "baseline" | "timeout":
            monkeypatch.setenv("MUTATION_OUTCOME", "failure")
            failed = Status(
                status="invalid" if failure == "baseline" else "incomplete",
                detail=failure,
                elapsed_seconds=1.0,
                source_unchanged=False,
            )
            _ = status.write_text(failed.model_dump_json())
        case "malformed":
            _ = status.write_text('{"status": "invented"}')
        case "missing":
            status.unlink()
        case "report":
            (campaign / "mutation/results.txt").unlink()
        case "mismatch":
            monkeypatch.setenv("MUTATION_OUTCOME", "failure")
        case "counts":
            _ = (campaign / "mutation/mutants/mutmut-cicd-stats.json").write_text("{}")
        case "sha":
            monkeypatch.setenv("GITHUB_SHA", "0" * 40)
        case "symlink":
            if sys.platform == "win32":
                pytest.skip("Unix symlink control")
            status.unlink()
            status.symlink_to(campaign / "uv.lock")
        case _:
            assert_never(failure)
    # When: the same exporter used by the workflow runs.
    result = command(campaign, "export")
    # Then: no missing/invalid evidence becomes a successful empty experiment.
    assert result.returncode != 0
    summary = (campaign / "summary.md").read_text()
    assert "Evidence rejected or unavailable" in summary or failure in {
        "baseline",
        "timeout",
    }
    assert "Status: complete" not in summary


def test_prepare_rejects_stale_results(campaign: Path) -> None:
    # Given: an existing campaign cannot be reused for a fresh dispatch.
    # When: preparation is repeated.
    result = command(campaign, "prepare")
    # Then: it refuses the existing output instead of caching a result.
    assert result.returncode != 0
