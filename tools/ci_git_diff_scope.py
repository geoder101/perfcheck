"""Classify a set of changed repository paths into a CI change scope.

Pure :func:`classify` and :func:`render` helpers plus a stdin-to-``$GITHUB_OUTPUT``
CLI that decides whether a push is documentation-only, a pure chore, or code. The
glob sets mirror :data:`tools.docs_inputs._DOC_INPUT_GLOBS` so the CI render
decision stays consistent with the local render cache.

Matching uses :meth:`pathlib.PurePath.full_match` (glob semantics) rather than
``fnmatch``: ``docs/**/*.rst`` matches the top-level ``docs/index.rst`` so a
single ``.rst`` change still renders the site.
"""

from __future__ import annotations

import enum
import os
import sys
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "CODE_GLOBS",
    "DOCS_ONLY_PATHS",
    "OTHER_PATHS",
    "Scope",
    "classify",
    "render",
]


class Scope(enum.StrEnum):
    """CI change scope tiers, resolved docs -> other -> code by :func:`classify`."""

    CODE = "code"
    DOCS = "docs"
    OTHER = "other"


# Paths that are provably documentation-only: a push touching only these renders
# the site and skips the heavy test/lint/type/coverage/build matrix.
DOCS_ONLY_PATHS: Final = (
    "docs/**/*.rst",
    "docs/**/*.md",
    "docs/_templates/**",
    "docs/_static/**",
    "**/*.md",
    "tools/docs/package*.json",
    "tools/docs/puppeteer*.json",
)

# Pure chore paths: neither documentation nor a gate. A push touching only these
# short-circuits with no jobs at all.
OTHER_PATHS: Final = (
    "LICENSE",
    "CHANGELOG.md",
    ".gitignore",
    ".oc-selector",
    ".config/oc-selector",
)

# Everything else that touches a gate (Python lint/type/test/build, deps, recipes,
# schema, CI, container adapter). classify defaults to CODE for any path that is
# neither provably docs-only nor a registered chore, so an unknown path can never
# silently skip a gate.
CODE_GLOBS: Final = (
    "src/**/*.py",
    "tests/**/*.py",
    "examples/**/*.py",
    "tools/**/*.py",
    "tools/*.sh",
    "tools/*.ps1",
    "docs/conf.py",
    "conftest.py",
    "pyproject.toml",
    "uv.lock",
    "justfile",
    "podman.just",
    "schemas/**",
    ".github/**",
    "Containerfile",
)


def _is_subset(changed: Iterable[str], globs: tuple[str, ...]) -> bool:
    """Return True when every changed path matches at least one glob in ``globs``."""
    return all(
        any(PurePosixPath(path).full_match(pattern) for pattern in globs)
        for path in changed
    )


def _intersects(changed: Iterable[str], globs: tuple[str, ...]) -> bool:
    """Return True when any changed path matches any glob in ``globs``."""
    return any(
        PurePosixPath(path).full_match(pattern) for path in changed for pattern in globs
    )


def classify(changed: Iterable[str]) -> Scope:
    """Resolve a changed-path set to a scope: docs, chore, or code.

    Docs is checked first, then chore, then code. An empty set resolves to chore
    so a no-op diff never runs the matrix.
    """
    paths = set(changed)
    if not paths:
        return Scope.OTHER
    if _is_subset(paths, DOCS_ONLY_PATHS):
        return Scope.DOCS
    if _is_subset(paths, OTHER_PATHS):
        return Scope.OTHER
    return Scope.CODE


def render(changed: Iterable[str]) -> bool:
    """Return True when a changed-path set intersects the docs render inputs.

    Mirrors :data:`tools.docs_inputs._DOC_INPUT_GLOBS`, which excludes ``.md``
    because Sphinx renders only ``.rst``.
    """
    return _intersects(
        set(changed),
        (
            "src/**/*.py",
            "docs/**/*.rst",
            "docs/conf.py",
            "docs/_templates/**",
            "docs/_static/**",
            "pyproject.toml",
            "uv.lock",
            "tools/mermaid.py",
            "tools/docs_inputs.py",
            "tools/docs_gate.py",
            "tools/docs/package*.json",
            "tools/docs/puppeteer*.json",
        ),
    )


def _read_changed_paths(stream: Iterable[str]) -> list[str]:
    """Return stripped, non-empty lines from ``stream`` as changed paths."""
    return [line.strip() for line in stream if line.strip()]


def _render_results(changed: Iterable[str]) -> tuple[str, str, str]:
    """Return the ``(scope, render, full_gate)`` string triple for ``changed``."""
    scope = classify(changed)
    rendered = render(changed)
    full_gate = scope == Scope.CODE
    return scope.value, str(rendered).lower(), str(full_gate).lower()


def main() -> int:
    """Read newline-separated changed paths from stdin and emit the scope triple.

    Writes ``scope``, ``render``, and ``full_gate`` to ``$GITHUB_OUTPUT`` when set,
    otherwise to stdout. No third-party imports and no imports of heavier
    ``tools.*`` modules.
    """
    changed = _read_changed_paths(sys.stdin)
    scope, rendered, full_gate = _render_results(changed)
    lines = f"scope={scope}\nrender={rendered}\nfull_gate={full_gate}\n"
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            _ = handle.write(lines)
    else:
        _ = sys.stdout.write(lines)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
