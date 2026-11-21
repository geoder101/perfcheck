from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]
_WORKFLOW: Final = _ROOT / ".github/workflows/pages.yml"
_SHA: Final = "a" * 40


def _script(step: str) -> str:
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    header = rf"      - name: {step}\n(?s:.*?)        run: \|\n"
    match = re.search(
        header + r"((?:          [^\n]*\n|\n)+)",
        workflow,
    )
    assert match, f"Missing executable workflow step: {step}"
    shell = "\n".join(line[10:] for line in match[1].splitlines()).strip()
    assert shell.startswith("python3 -I - <<'PY'\n")
    assert shell.endswith("\nPY")
    return shell.split("\n", 1)[1].removesuffix("\nPY")


@pytest.mark.parametrize(
    ("event", "ref", "branch", "expected"),
    [
        ("push", "refs/heads/trunk", "trunk", 0),
        ("workflow_dispatch", "refs/heads/release/docs", "release/docs", 0),
        ("push", "refs/heads/topic", "trunk", 1),
        ("workflow_dispatch", "refs/heads/topic", "trunk", 1),
        ("workflow_dispatch", "refs/tags/trunk", "trunk", 1),
        ("pull_request", "refs/heads/trunk", "trunk", 1),
        ("pull_request_target", "refs/heads/trunk", "trunk", 1),
        ("workflow_run", "refs/heads/trunk", "trunk", 1),
        ("push", "refs/heads/", "", 1),
        ("push", "refs/heads/trunk\nbuild=true", "trunk", 1),
    ],
)
def test_inline_authorization_blocks_untrusted_builds(
    event: str, ref: str, branch: str, expected: int, tmp_path: Path
) -> None:
    # Given: event context and observable downstream installation/build commands.
    output = tmp_path / "output"
    marker = tmp_path / "installed-or-built"
    environment = {
        **os.environ,
        "EVENT_NAME": event,
        "EVENT_REF": ref,
        "DEFAULT_BRANCH": branch,
        "EVENT_SHA": _SHA,
        "GITHUB_OUTPUT": str(output),
    }
    environment["BUILD_MARKER"] = str(marker)
    script = _script("Authorize event") + '\nPath(os.environ["BUILD_MARKER"]).touch()\n'

    # When: the actual workflow's inline authorization executes, without checkout.
    result = subprocess.run(  # noqa: S603 - execute the owned workflow policy verbatim.
        [sys.executable, "-I", "-c", script],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    # Then: denial is a failure, never a successful empty deployment.
    assert result.returncode == expected, result.stderr
    assert marker.exists() == (expected == 0)
    assert output.exists() == (expected == 0)
    if expected == 0:
        assert output.read_text() == f"trusted=true\nsha={_SHA}\n"


@pytest.mark.parametrize("sha", ["", "trunk", "a" * 39, "g" * 40, _SHA + "\nx=y"])
def test_inline_authorization_rejects_malformed_sha(sha: str, tmp_path: Path) -> None:
    # Given: a trusted branch but invalid immutable revision input.
    environment = {
        **os.environ,
        "EVENT_NAME": "push",
        "EVENT_REF": "refs/heads/trunk",
        "DEFAULT_BRANCH": "trunk",
        "EVENT_SHA": sha,
        "GITHUB_OUTPUT": str(tmp_path / "output"),
    }
    # When: the workflow authorizes the event.
    result = subprocess.run(  # noqa: S603 - execute the owned workflow policy verbatim.
        [sys.executable, "-I", "-c", _script("Authorize event")],
        env=environment,
        capture_output=True,
        check=False,
        timeout=10,
    )
    # Then: invalid context cannot manufacture build outputs.
    assert result.returncode != 0
    assert not (tmp_path / "output").exists()


def test_pages_workflow_has_fail_closed_job_wiring() -> None:
    # Given: the real workflow configuration.
    workflow = _WORKFLOW.read_text(encoding="utf-8")
    # When: job boundaries and privileged publication are inspected.
    authorization, build, deploy = re.split(r"\n  (?:build|deploy):\n", workflow)
    # Then: source execution follows authorization and deployment follows build.
    assert "uses:" not in authorization
    assert "needs: authorize" in build
    assert "if: needs.authorize.outputs.trusted == 'true'" in build
    assert "ref: ${{ needs.authorize.outputs.sha }}" in build
    assert "persist-credentials: false" in build
    # Regression guard (IS-4): the tautological "Verify checkout" re-check stays gone.
    assert "Verify checkout" not in build
    assert "just sync" in build
    assert "just docs-check\n" in build
    assert "python -m tools.pages_authorization" in build
    assert "path: docs/_build/html\n" in build
    assert "needs: build" in deploy
    assert "pages: write" not in authorization + build
    assert "id-token: write" not in authorization + build
    assert "contents: read\n      pages: write\n      id-token: write" in deploy
    assert "name: github-pages" in deploy
    assert "url: ${{ steps.deployment.outputs.page_url }}" in deploy
    assert "group: github-pages\n  cancel-in-progress: false" in workflow
    assert "on:\n  push:\n  workflow_dispatch:\n" in workflow
    assert all(
        term not in workflow
        for term in (
            "pull_request",
            "workflow_run",
            "continue-on-error",
            "always()",
            "--all-groups",
            "coverage/",
            "mutation/",
            "secrets.",
        )
    )


def test_pages_action_sha_pins_match_verified_official_releases() -> None:
    # Given: live-verified immutable commit SHAs and their release tags. The
    # setup-uv/setup-just pins now live in the shared toolchain action, so the
    # pages workflow only references checkout and the render toolchain inline.
    expected = [
        ("actions/checkout", "3d3c42e5aac5ba805825da76410c181273ba90b1", "v7.0.1"),
        ("actions/setup-node", "949feb2413d6458794dcd2491c4babbbce0c15c1", "v7.1.0"),
        (
            "actions/upload-pages-artifact",
            "fc324d3547104276b827a68afc52ff2a11cc49c9",
            "v5.0.0",
        ),
        ("actions/deploy-pages", "368f82528645a54fb793d4d04e342629a3f51346", "v5.0.1"),
    ]
    # When: every action reference is extracted with its release tag comment.
    compiled = re.compile(r"uses: ([^@\s]+)@([0-9a-f]{40})(?:\s+#\s+(\S+))?")
    actual = [
        (match.group(1), match.group(2), match.group(3))
        for match in compiled.finditer(_WORKFLOW.read_text(encoding="utf-8"))
    ]
    # Then: only the exact verified SHAs execute, each remembered with its release tag.
    assert actual == expected
