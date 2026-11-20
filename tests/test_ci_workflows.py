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
    "astral-sh/setup-uv": "07a047e608db84b3d8c06cd9a7c7dcc9c355c18e",
    "extractions/setup-just": "53165ef7e734c5c07cb06b3c8e7b647c5aa16db3",
    "actions/upload-artifact": "cf430e030ddbb5b0abf93d22962f4752f3646cd9",
    "actions/setup-node": "949feb2413d6458794dcd2491c4babbbce0c15c1",
    "actions/upload-pages-artifact": "fc324d3547104276b827a68afc52ff2a11cc49c9",
    "actions/deploy-pages": "368f82528645a54fb793d4d04e342629a3f51346",
}

EXPECTED_TAG: Final[dict[str, str]] = {
    "actions/checkout": "v7.0.1",
    "astral-sh/setup-uv": "v10.3.2",
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


def test_ci_pages_and_mutation_actions_are_sha_pinned() -> None:
    # Given: all hosted workflows, pinned to immutable commit SHAs rather than
    # floating major/version tags.
    workflows = {
        "ci": (_ROOT / ".github/workflows/ci.yml").read_text(),
        "pages": (_ROOT / ".github/workflows/pages.yml").read_text(),
        "mutation": (_ROOT / ".github/workflows/mutation.yml").read_text(),
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
    # Given: the fast Linux gate, the merge-time full check, and the coverage sweep.
    workflow = (_ROOT / ".github/workflows/ci.yml").read_text()
    pages = (
        (_ROOT / ".github/workflows/pages.yml").read_text().split("\n  deploy:\n")[0]
    )
    check_block, docs_block, coverage_block = _job_blocks(workflow)
    # When/Then: the Mermaid/Chrome/LaTeX toolchain is provisioned before the checks
    # that consume it — the merge-time full check and the coverage sweep — while the
    # fast gate deliberately renders nothing.
    for block, gate in (
        (docs_block, "run: just check"),
        (coverage_block, "run: just coverage-check"),
    ):
        assert 'node-version: "24.18.0"' in block
        assert block.index("npm ci --prefix tools/docs --ignore-scripts") < block.index(
            gate
        )
        browser_cli = "node tools/docs/node_modules/puppeteer/lib/puppeteer/node/cli.js"
        assert block.index(f"{browser_cli} browsers install chrome") < block.index(gate)
        assert "texlive-latex-extra" in block
        assert "dvisvgm" in block
        assert "apparmor_parser" in block
        assert "--no-sandbox" not in block
        assert "sysctl" not in block

    # The fast gate runs without any rendering provisioning.
    assert "npm ci --prefix tools/docs" not in check_block
    assert "texlive-latex-extra" not in check_block
    assert "apparmor_parser" not in check_block

    # Pages provisions the same toolchain before its docs build.
    assert pages.index("npm ci --prefix tools/docs --ignore-scripts") < pages.index(
        "just docs-check"
    )
    assert pages.index("apparmor_parser") < pages.index("just docs-check")


def test_ci_pages_and_mutation_forbid_insecure_gating_and_leaked_credentials() -> None:
    # Given: the hosted workflows, checked for insecure or leaky constructs.
    workflows = {
        "ci": (_ROOT / ".github/workflows/ci.yml").read_text(),
        "pages": (_ROOT / ".github/workflows/pages.yml").read_text(),
        "mutation": (_ROOT / ".github/workflows/mutation.yml").read_text(),
    }
    # When/Then: no workflow may use privileged triggers, leaked secrets, external
    # reporters, or coverage/mutation opt-outs. The mutation pilot legitimately
    # installs the mutation group, so that one token is excluded only there.
    for name, workflow in workflows.items():
        forbidden = (
            tuple(t for t in FORBIDDEN_TOKENS if t != "--group mutation")
            if name == "mutation"
            else FORBIDDEN_TOKENS
        )
        for token in forbidden:
            assert token not in workflow, f"{name}: forbidden {token!r} present"
