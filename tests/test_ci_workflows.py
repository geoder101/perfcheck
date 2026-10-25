from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).parents[1]


def test_ci_preserves_matrix_and_fixed_separate_coverage_gate() -> None:
    # Given: the executable CI workflow, not a disconnected policy fixture.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    # When: ordinary and measurement job boundaries are inspected.
    ordinary, coverage = workflow.split("\n  coverage:\n")
    # Then: ordinary checks stay coverage-free on all three supported platforms.
    assert "on:\n  pull_request:\n  push:\n" in ordinary
    assert "permissions:\n  contents: read\n" in ordinary
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" in ordinary
    assert "fail-fast: false" in ordinary
    assert "      - run: just check\n" in ordinary
    assert "coverage-check" not in ordinary
    assert "runs-on: ubuntu-latest" in coverage
    assert "id: gate\n        run: just coverage-check\n" in coverage
    assert "GATE_OUTCOME: ${{ steps.gate.outcome }}" in coverage
    assert 'export --outcome "$GATE_OUTCOME"' in coverage
    assert "exit 1" in coverage
    assert coverage.count("if: always()") == 2
    assert "id: evidence" in coverage
    assert "if: always() && steps.evidence.outputs.publish == 'true'" in coverage
    assert "PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in coverage
    assert "run: uv run python -m tools.quality_evidence prepare" in coverage
    assert coverage.index("prepare\n") < coverage.index("run: just coverage-check")
    assert all(
        forbidden not in workflow
        for forbidden in (
            "continue-on-error",
            "--all-groups",
            "--group mutation",
            "secrets.",
            "pull_request_target",
            "workflow_run",
            "contents: write",
            "codecov",
        )
    )
    for job in (ordinary, coverage):
        assert 'python-version: "3.14"' in job
        assert 'just-version: "1.58.0"' in job
        assert "uv sync --locked --group dev --group docs --group examples" in job
        assert "ref: ${{ github.sha }}" in job
        assert "persist-credentials: false" in job


def test_ci_pins_and_artifact_allowlist_match_official_release_receipts() -> None:
    # Given: release provenance receipts from tasks 5 and 6.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    expected = {
        "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
        "astral-sh/setup-uv": "07a047e608db84b3d8c06cd9a7c7dcc9c355c18e",
        "extractions/setup-just": "53165ef7e734c5c07cb06b3c8e7b647c5aa16db3",
        "actions/upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    }
    # When: action references and the upload input block are extracted.
    actions = list(re.finditer(r"uses: ([^@\s]+)@([^\s]+)", workflow))
    upload = workflow.split("      - name: Retain coverage evidence\n")[1]
    # Then: hidden data is explicitly selected without exposing the workspace.
    assert len(actions) == 7
    assert all(expected[action[1]] == action[2] for action in actions)
    assert "include-hidden-files: true" in upload
    assert "retention-days: 7" in upload
    assert "if-no-files-found: warn" in upload
    paths = re.findall(r"^            (.+)$", upload, re.MULTILINE)
    assert paths == [
        "coverage/evidence/html/",
        "coverage/evidence/coverage.json",
        "coverage/evidence/.coverage",
        "coverage/evidence/provenance.json",
        "coverage/evidence/start.json",
    ]
