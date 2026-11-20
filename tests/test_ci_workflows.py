from __future__ import annotations

import re
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).parents[1]

# Immutable commit SHAs (with the release tag remembered in a trailing comment)
# that every hosted workflow must pin its actions to. Resolved from official
# releases; a floating major/version tag must never be used again.
EXPECTED_SHA: Final[dict[str, str]] = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
    "astral-sh/setup-uv": "1db35dd8eee11c5894872e0b383ae6c406cf738d",
    "extractions/setup-just": "53165ef7e734c5c07cb06b3c8e7b647c5aa16db3",
    "actions/upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    "actions/setup-node": "949feb2413d6458794dcd2491c4babbbce0c15c1",
    "actions/upload-pages-artifact": "fc324d3547104276b827a68afc52ff2a11cc49c9",
    "actions/deploy-pages": "368f82528645a54fb793d4d04e342629a3f51346",
}

EXPECTED_TAG: Final[dict[str, str]] = {
    "actions/checkout": "v7.0.1",
    "astral-sh/setup-uv": "v10.4.0",
    "extractions/setup-just": "v4.0.0",
    "actions/upload-artifact": "v7.0.2",
    "actions/setup-node": "v7.1.0",
    "actions/upload-pages-artifact": "v5.0.0",
    "actions/deploy-pages": "v5.0.1",
}

# Forbidden across hosted workflows: privileged/insecure triggers, leaked
# credentials, coverage/mutation opt-ins, and external coverage reporters.
FORBIDDEN_TOKENS: Final[tuple[str, ...]] = (
    "continue-on-error",
    "--all-groups",
    "--group mutation",
    "secrets.",
    "pull_request_target",
    "workflow_run",
    "contents: write",
    "codecov",
)

# Workflows that legitimately require exactly one forbidden token for a bounded,
# documented reason. Each exception is scoped to a single token and grants nothing
# beyond it; no other workflow may use the token.
# - mutation installs the optional mutation group to run the bounded pilot.
# - release writes a GitHub Release and references the PyPI token to publish.
TOKEN_EXCEPTIONS: Final[dict[str, tuple[str, ...]]] = {
    "mutation": ("--group mutation",),
    "release": ("contents: write", "secrets."),
}


def _job_blocks(workflow: str) -> tuple[str, str, str]:
    # Given a ci.yml body, split it into the check, docs, and coverage job blocks
    # by their two-space indented headers, which are unique within the file.
    check_block = workflow.split("\n  check:\n", 1)[1].split("\n  docs:\n", 1)[0]
    docs_block = workflow.split("\n  docs:\n", 1)[1].split("\n  coverage:\n", 1)[0]
    coverage_block = workflow.split("\n  coverage:\n", 1)[1]
    return check_block, docs_block, coverage_block


def test_ci_faster_linux_gate_docs_merged_and_coverage_scheduled() -> None:
    # Given: the restructured CI workflow — a fast Linux PR gate, a merge-time full
    # check, and a coverage sweep that runs off the push/PR path.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    on_block, check_block, docs_block, coverage_block = (
        workflow.split("jobs:", 1)[0],
        *_job_blocks(workflow),
    )
    # When: ordinary, merge, and measurement job boundaries are inspected.
    # Then: the trigger list stays ordered push-first and jobs are gated individually.
    assert "on:\n  pull_request:\n  push:\n" in on_block
    assert "schedule:" in on_block
    assert "workflow_dispatch:" in on_block
    assert "permissions:\n  contents: read\n" in on_block
    # The three-OS matrix is gone; nothing hard-gates a run on an OS.
    assert "os: [ubuntu-latest, macos-latest, windows-latest]" not in workflow
    assert "fail-fast: false" not in workflow

    # The fast gate is Linux-only and runs the lightweight recipe.
    assert "runs-on: ubuntu-latest" in check_block
    assert "if: github.event_name != 'schedule'" in check_block
    assert "run: just fast-check" in check_block
    assert "just check" not in check_block
    assert "just coverage-check" not in check_block

    # The full check runs after merge on the default branch (skipped on PRs/schedules).
    assert "runs-on: ubuntu-latest" in docs_block
    assert "if: github.event_name != 'schedule'" in docs_block
    assert (
        "format('refs/heads/{0}', github.event.repository.default_branch)" in docs_block
    )
    assert "run: just check" in docs_block
    assert "just fast-check" not in docs_block

    # The coverage sweep runs on schedule or manual dispatch with a generous timeout.
    assert (
        "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
        in coverage_block
    )
    assert "timeout-minutes: 30" in coverage_block
    assert "id: gate\n        run: just coverage-check" in coverage_block
    assert 'export --outcome "$GATE_OUTCOME"' in coverage_block
    assert coverage_block.count("if: always()") == 2
    assert "id: evidence" in coverage_block
    assert "if: always() && steps.evidence.outputs.publish == 'true'" in coverage_block
    assert "PR_HEAD_SHA: ${{ github.event.pull_request.head.sha }}" in coverage_block
    assert "run: uv run python -m tools.quality_evidence prepare" in coverage_block
    assert coverage_block.index("prepare\n") < coverage_block.index(
        "run: just coverage-check"
    )


def test_ci_release_pages_and_mutation_actions_are_sha_pinned() -> None:
    # Given: all hosted workflows, pinned to immutable commit SHAs rather than
    # floating major/version tags.
    workflows = {
        "ci": (_ROOT / ".github/workflows/ci.yml").read_text(),
        "pages": (_ROOT / ".github/workflows/pages.yml").read_text(),
        "mutation": (_ROOT / ".github/workflows/mutation.yml").read_text(),
        "release": (_ROOT / ".github/workflows/release.yml").read_text(),
    }
    # When: every action reference across all workflows is parsed.
    pattern = re.compile(r"uses:\s+([^/\s@]+/[^/\s@]+)@([0-9a-f]{40})(?:\s+#\s+(\S+))?")
    for name, workflow in workflows.items():
        references = list(pattern.finditer(workflow))
        # Then: each reference is the expected SHA with a matching tag comment, and
        # no floating tag survives.
        assert references, f"{name} workflow references no actions"
        for action, ref, comment in (
            (m.group(1), m.group(2), m.group(3)) for m in references
        ):
            assert action in EXPECTED_SHA, f"{name}: unexpected action {action!r}"
            assert ref == EXPECTED_SHA[action], (
                f"{name}: {action} sha {ref!r} != {EXPECTED_SHA[action]}"
            )
            assert comment == EXPECTED_TAG[action], (
                f"{name}: {action} tag comment {comment!r} != {EXPECTED_TAG[action]}"
            )


def test_docs_and_coverage_render_toolchain_provisioned_before_check() -> None:
    # Given: the fast Linux gate, the merge-time full check, and the coverage sweep,
    # all delegating the Mermaid/Chrome/LaTeX toolchain to a reusable action.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    pages = (
        (_ROOT / ".github/workflows/pages.yml").read_text().split("\n  deploy:\n")[0]
    )
    check_block, docs_block, coverage_block = _job_blocks(workflow)
    render = (_ROOT / ".github/actions/provision-docs-render/action.yml").read_text()
    # When/Then: every render-consuming job invokes the action before its check, the
    # fast gate deliberately renders nothing, and the action installs the real
    # Node/Chrome/LaTeX toolchain without widening Chrome's apparmor sandbox.
    for block, gate in (
        (docs_block, "run: just check"),
        (coverage_block, "run: just coverage-check"),
    ):
        assert 'node-version: "24.18.0"' in block
        assert "uses: ./.github/actions/provision-docs-render" in block
        assert block.index(
            "uses: ./.github/actions/provision-docs-render"
        ) < block.index(gate)

    # The fast gate runs without any rendering provisioning.
    assert "provision-docs-render" not in check_block

    # Pages invokes the same action before its docs build.
    assert "uses: ./.github/actions/provision-docs-render" in pages
    assert pages.index("uses: ./.github/actions/provision-docs-render") < pages.index(
        "just docs-check"
    )

    # The action installs the toolchain and leaves Chrome's sandbox apparmor intact.
    assert "npm ci --prefix tools/docs --ignore-scripts" in render
    assert "browsers install chrome" in render
    assert "texlive-latex-extra" in render
    assert "dvisvgm" in render
    assert "sudo apparmor_parser -r /etc/apparmor.d/perfcheck-chrome" in render
    assert "--no-sandbox" not in render
    assert "sysctl" not in render


def test_hosted_workflows_forbid_insecure_gating_and_leaked_credentials() -> None:
    # Given: the hosted workflows, checked for insecure or leaky constructs.
    workflows = {
        "ci": (_ROOT / ".github/workflows/ci.yml").read_text(),
        "pages": (_ROOT / ".github/workflows/pages.yml").read_text(),
        "mutation": (_ROOT / ".github/workflows/mutation.yml").read_text(),
        "release": (_ROOT / ".github/workflows/release.yml").read_text(),
    }
    # When/Then: no workflow may use privileged triggers, leaked secrets, external
    # reporters, or coverage/mutation opt-outs. Each workflow in TOKEN_EXCEPTIONS is
    # granted only the single token it genuinely needs.
    for name, workflow in workflows.items():
        exceptions = TOKEN_EXCEPTIONS.get(name, ())
        forbidden = tuple(t for t in FORBIDDEN_TOKENS if t not in exceptions)
        for token in forbidden:
            assert token not in workflow, f"{name}: forbidden {token!r} present"
