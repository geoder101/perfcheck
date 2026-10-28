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


def test_ci_tags_and_artifact_allowlist_match_verified_official_releases() -> None:
    # Given: live-verified exact stable release tags.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    expected = {
        "actions/checkout": "v7.0.1",
        "astral-sh/setup-uv": "v10.3.2",
        "extractions/setup-just": "v4.0.0",
        "actions/upload-artifact": "v7.0.2",
        "actions/setup-node": "v7.1.0",
    }
    # When: action references and the upload input block are extracted.
    actions = list(re.finditer(r"uses: ([^@\s]+)@([^\s]+)", workflow))
    upload = workflow.split("      - name: Retain coverage evidence\n")[1]
    # Then: hidden data is explicitly selected without exposing the workspace.
    assert len(actions) == 9
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


def test_render_toolchain_is_provisioned_before_checks() -> None:
    # Given: ordinary three-OS checks and the separate Linux coverage job.
    ordinary, coverage = (
        (_ROOT / ".github/workflows/ci.yml").read_text().split("\n  coverage:\n")
    )
    pages = (
        (_ROOT / ".github/workflows/pages.yml").read_text().split("\n  deploy:\n")[0]
    )
    # When/Then: provision the exact local tools and regular Chrome before use.
    for job, gate in (
        (ordinary, "run: just check"),
        (coverage, "run: just coverage-check"),
        (pages, "just docs-check"),
    ):
        assert 'node-version: "24.18.0"' in job
        assert job.index("npm ci --prefix tools/docs --ignore-scripts") < job.index(
            gate
        )
        browser_cli = "node tools/docs/node_modules/puppeteer/lib/puppeteer/node/cli.js"
        assert job.index(f"{browser_cli} browsers install chrome") < job.index(gate)
        assert "texlive-latex-extra" in job
        assert "dvisvgm" in job
        assert "--no-sandbox" not in job
        assert "apparmor_parser" in job
        assert "sysctl" not in job
    assert "brew install --cask basictex" in ordinary
    assert "tlmgr install" in ordinary
    assert "preview" in ordinary
    assert "choco install miktex" in ordinary
    assert pages.index("Verify checkout") < pages.index("actions/setup-node@")


def test_windows_installs_real_miktex_converter_and_command_links() -> None:
    # Given: Windows MiKTeX uses its platform-specific binary package ID.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    windows = workflow.split("- name: Provision Windows TeX")[1].split(
        "- run: just check"
    )[0]
    # When/Then: install the binary, expose dvisvgm, and verify command discovery.
    assert "miktex-dvisvgm-bin-x64-2.9" in windows
    assert "miktex --admin links install --force" in windows
    assert "latex --version" in windows
    assert "dvisvgm --version" in windows
