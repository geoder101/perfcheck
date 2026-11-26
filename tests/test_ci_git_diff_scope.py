"""Behavioral coverage for the CI change-scope classifier and its CLI.

Each test is structured with explicit ``Given``/``When``/``Then`` comments: the
``When`` is one observable action (a call to :func:`classify`, :func:`render`, or
the CLI) and the ``Then`` asserts the public contract. Cases are parametrized over
the representative changed-path sets from the plan's ``§5.7``.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest
from tools.ci_git_diff_scope import Scope, classify, main, render

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

# Representative single-path sets: (changed paths, expected scope).
CLASSIFY_SINGLE: list[tuple[list[str], Scope]] = [
    (["docs/how-to/x.rst"], Scope.DOCS),
    (["docs/index.rst"], Scope.DOCS),  # top-level .rst, guards against fnmatch
    (["docs/explanation/y.rst"], Scope.DOCS),
    (["docs/README.md"], Scope.DOCS),
    (["examples/README.md"], Scope.DOCS),
    (["tools/docs/package.json"], Scope.DOCS),
    (["docs/conf.py"], Scope.CODE),  # hits the Python gate, not docs-only
    (["src/perfcheck/cli.py"], Scope.CODE),
    (["examples/01-overview.py"], Scope.CODE),
    (["tools/mermaid.py"], Scope.CODE),
    (["tools/ci_git_diff_scope.py"], Scope.CODE),
    ([".github/workflows/ci.yml"], Scope.CODE),
    (["schemas/v1/perfcheck-policy.schema.json"], Scope.CODE),
    (["unknown/path/file.txt"], Scope.CODE),  # unknown => default-to-code
    (["LICENSE"], Scope.OTHER),
    ([".gitignore"], Scope.OTHER),
]

# Representative mixed sets: (changed paths, expected scope).
CLASSIFY_MIXED: list[tuple[list[str], Scope]] = [
    (["docs/a.rst", "src/x.py"], Scope.CODE),  # docs + code => code (matrix runs)
    (["docs/a.rst", "README.md"], Scope.DOCS),  # docs + prose => docs
    (["docs/a.rst", "LICENSE"], Scope.CODE),  # docs + chore => code (safe default)
    (["LICENSE", ".gitignore"], Scope.OTHER),  # pure chore => other
]

# Representative render-input sets: (changed paths, expected render flag).
RENDER: list[tuple[list[str], bool]] = [
    (["docs/how-to/x.rst"], True),  # .rst renders
    (["docs/index.rst"], True),  # top-level .rst renders (guards against fnmatch)
    (["docs/conf.py"], True),
    (["src/perfcheck/cli.py"], True),
    (["tools/mermaid.py"], True),
    (["tools/docs/package.json"], True),
    (["examples/README.md"], False),  # prose is not rendered
    (["README.md"], False),
    ([".gitignore"], False),
]

# CLI cases: (changed paths, exact stdout triple). Exercises the full-gate
# invariant ``full_gate == (scope == code)`` through the real CLI output.
CLI_CASES: list[tuple[list[str], str]] = [
    (["docs/how-to/x.rst"], "scope=docs\nrender=true\nfull_gate=false\n"),
    (["docs/index.rst"], "scope=docs\nrender=true\nfull_gate=false\n"),
    (["docs/conf.py"], "scope=code\nrender=true\nfull_gate=true\n"),
    (["src/perfcheck/cli.py"], "scope=code\nrender=true\nfull_gate=true\n"),
    (["tools/mermaid.py"], "scope=code\nrender=true\nfull_gate=true\n"),
    (["tools/docs/package.json"], "scope=docs\nrender=true\nfull_gate=false\n"),
    (["examples/README.md"], "scope=docs\nrender=false\nfull_gate=false\n"),
    (["README.md"], "scope=docs\nrender=false\nfull_gate=false\n"),
    (["LICENSE"], "scope=other\nrender=false\nfull_gate=false\n"),
    ([".gitignore"], "scope=other\nrender=false\nfull_gate=false\n"),
    (["unknown/path/file.txt"], "scope=code\nrender=false\nfull_gate=true\n"),
    (["docs/a.rst", "src/x.py"], "scope=code\nrender=true\nfull_gate=true\n"),
    (["docs/a.rst", "README.md"], "scope=docs\nrender=true\nfull_gate=false\n"),
    ([], "scope=other\nrender=false\nfull_gate=false\n"),
]


def _classify(changed: Iterable[str]) -> Scope:
    """Resolve ``changed`` to a scope through the classifier under test."""
    return classify(changed)


@pytest.mark.parametrize(("changed", "expected"), CLASSIFY_SINGLE)
def test_classify_single_path_sets(changed: list[str], expected: Scope) -> None:
    # Given: a single changed path, ``changed``.
    # When: it is classified.
    actual = _classify(changed)
    # Then: it resolves to the expected scope tier.
    assert actual == expected


@pytest.mark.parametrize(
    ("changed", "expected"),
    CLASSIFY_MIXED,
)
def test_classify_mixed_sets(changed: list[str], expected: Scope) -> None:
    # Given: a changed set spanning more than one tier.
    # When: it is classified.
    actual = _classify(changed)
    # Then: the ordering docs -> other -> code decides the tier.
    assert actual == expected


def test_classify_empty_set_resolves_to_other() -> None:
    # Given: an empty changed set (a no-op diff).
    # When: it is classified.
    actual = _classify([])
    # Then: it resolves to chore so a no-op diff never runs the matrix.
    assert actual == Scope.OTHER


@pytest.mark.parametrize(("changed", "expected"), RENDER)
def test_render_predicate(changed: list[str], expected: bool) -> None:
    # Given: a changed set, ``changed``.
    # When: the render predicate is evaluated.
    actual = render(changed)
    # Then: it is true only for inputs Sphinx re-renders (excludes prose/chore).
    assert actual == expected


@pytest.mark.parametrize(("changed", "expected"), CLI_CASES)
def test_cli_emits_scope_render_full_gate(
    changed: list[str],
    expected: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: changed paths on stdin.
    monkeypatch.setattr("sys.stdin", io.StringIO("\n".join(changed) + "\n"))
    # When: the CLI runs.
    exit_code = main()
    # Then: it exits 0 and writes the exact scope/render/full_gate triple to stdout.
    assert exit_code == 0
    assert capsys.readouterr().out == expected


def test_cli_writes_to_github_output_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: $GITHUB_OUTPUT pointing at a fresh file and a docs change on stdin.
    output_file = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))
    monkeypatch.setattr("sys.stdin", io.StringIO("docs/a.rst\n"))
    # When: the CLI runs.
    exit_code = main()
    # Then: the triple is appended to the output file and nothing goes to stdout.
    assert exit_code == 0
    assert output_file.read_text(encoding="utf-8") == (
        "scope=docs\nrender=true\nfull_gate=false\n"
    )
    assert capsys.readouterr().out == ""


def test_cli_is_idempotent_across_runs(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: a code change on stdin.
    monkeypatch.setattr("sys.stdin", io.StringIO("src/perfcheck/cli.py\n"))
    # When: the CLI runs twice over fresh stdin each time.
    _ = main()
    first = capsys.readouterr().out
    monkeypatch.setattr("sys.stdin", io.StringIO("src/perfcheck/cli.py\n"))
    _ = main()
    second = capsys.readouterr().out
    # Then: the output is byte-identical on each run.
    assert first == second == "scope=code\nrender=true\nfull_gate=true\n"


def test_cli_handles_crlf_and_blank_lines(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: CRLF-terminated paths with blank lines and surrounding whitespace.
    monkeypatch.setattr(
        "sys.stdin",
        io.StringIO("docs/how-to/x.rst\r\n\r\n   README.md   \r\n"),
    )
    # When: the CLI runs.
    _ = main()
    # Then: blank lines drop and each path is stripped before classify.
    assert capsys.readouterr().out == "scope=docs\nrender=true\nfull_gate=false\n"


def test_cli_preserves_spaces_in_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: a path containing internal spaces.
    monkeypatch.setattr("sys.stdin", io.StringIO("docs/my file.rst\n"))
    # When: the CLI runs.
    _ = main()
    # Then: internal spaces survive; the path still classifies as docs.
    assert capsys.readouterr().out == "scope=docs\nrender=true\nfull_gate=false\n"
