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
# - release writes a GitHub Release using the built-in token and contents: write.
TOKEN_EXCEPTIONS: Final[dict[str, tuple[str, ...]]] = {
    "mutation": ("--group mutation",),
    "release": ("contents: write", "secrets."),
}


def test_ci_release_pages_and_mutation_actions_are_sha_pinned() -> None:
    # Given: all hosted workflows, pinned to immutable commit SHAs rather than
    # floating major/version tags.
    workflows = {
        "ci": (_ROOT / ".github/workflows/ci.yml").read_text(),
        "pages": (_ROOT / ".github/workflows/pages.yml").read_text(),
        "mutation": (_ROOT / ".github/workflows/mutation.yml").read_text(),
        "release": (_ROOT / ".github/workflows/release.yml").read_text(),
        "setup": (_ROOT / ".github/actions/setup/action.yml").read_text(),
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
