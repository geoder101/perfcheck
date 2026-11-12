from __future__ import annotations

from pathlib import Path

import pytest

from tests import examples_check
from tests.examples_check import EXAMPLE_NOTEBOOKS, run_standalone_notebook

_ROOT = Path(__file__).parents[1]
_BLOB_PREFIX = "https://github.com/geoder101/perfcheck/blob/main/"
_LESSON_PATHS = EXAMPLE_NOTEBOOKS
_LESSON_OUTPUT_EVIDENCE = (
    (_LESSON_PATHS[0], "collect"),
    (_LESSON_PATHS[1], "metric_record_count"),
    (_LESSON_PATHS[2], "eligibility"),
    (_LESSON_PATHS[3], '"suite_status": "pass"'),
    (
        _LESSON_PATHS[4],
        (
            "Handled failure: exit status 3 — "
            "error: output path already exists; use --force to replace it"
        ),
    ),
    (_LESSON_PATHS[5], "sampling-distribution center"),
    (_LESSON_PATHS[6], "Rejected evidence: eligible=false, reason=gap_too_large"),
    (_LESSON_PATHS[7], "Reference advisory:"),
    (_LESSON_PATHS[8], "reference_quantile=-25.250"),
    (_LESSON_PATHS[9], "posterior=Beta(4,2)"),
)


@pytest.mark.parametrize("lesson_path", _LESSON_PATHS)
def test_curriculum_scope_has_standalone_marimo_scripts_in_teaching_order(
    lesson_path: Path,
) -> None:
    # Given: one lesson from the first curriculum segment.

    # When: its source is inspected as a notebook script.
    source = lesson_path.read_text(encoding="utf-8")

    # Then: it has the stable section order and the executable Marimo boundary.
    sections = ("## Goal", "## Inputs", "## Run", "## Evidence", "## Takeaway")
    positions = tuple(source.index(section) for section in sections)
    assert positions == tuple(sorted(positions))
    assert "app = marimo.App(" in source
    assert "@app.cell" in source
    assert 'if __name__ == "__main__":' in source
    assert "app.run()" in source
    assert "# /// script" not in source


@pytest.mark.parametrize(("lesson_path", "expected_evidence"), _LESSON_OUTPUT_EVIDENCE)
def test_no_generated_example_output_persists_after_lesson_execution(
    lesson_path: Path,
    expected_evidence: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an isolated current directory and a fake parent credential.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    example_paths_before = tuple(
        sorted(path.relative_to(_ROOT) for path in (_ROOT / "examples").rglob("*"))
    )

    # When: the public checker runs the absolute notebook in a fresh workspace.
    result = run_standalone_notebook(lesson_path)

    # Then: it succeeds and only renders the stable teaching headings.
    assert result.returncode == 0, result.stderr
    assert "Goal" in result.stdout
    assert "Takeaway" in result.stdout
    assert expected_evidence in result.stdout
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr
    assert (
        tuple(
            sorted(path.relative_to(_ROOT) for path in (_ROOT / "examples").rglob("*"))
        )
        == example_paths_before
    )


def test_curriculum_index_lists_each_lesson_once_in_numeric_order() -> None:
    # Given: the public curriculum index and the canonical lesson tuple.
    index = (_ROOT / "examples/README.md").read_text(encoding="utf-8")

    # When: each canonical lesson link is inspected.
    lesson_links = tuple(
        f"[{notebook.name}]({notebook.name})" for notebook in EXAMPLE_NOTEBOOKS
    )

    # Then: every lesson is linked once, in the teaching order.
    assert all(index.count(link) == 1 for link in lesson_links)
    assert tuple(index.index(link) for link in lesson_links) == tuple(
        sorted(index.index(link) for link in lesson_links)
    )


@pytest.mark.parametrize(
    ("index_path", "page"),
    [
        ("docs/explanation/index.rst", "learning-paths"),
        ("docs/explanation/index.rst", "probability-and-distributions"),
        ("docs/explanation/index.rst", "experimental-design"),
        ("docs/explanation/index.rst", "inference-and-power"),
        ("docs/explanation/index.rst", "multiple-testing"),
        ("docs/tutorials/index.rst", "performance-verification-case-study"),
    ],
)
def test_learning_pages_when_integrated_have_one_toctree_entry(
    index_path: str, page: str
) -> None:
    # Given: a completed educational page and its owning documentation index.
    source = (_ROOT / index_path).read_text(encoding="utf-8")
    # When: the toctree entries are read.
    entries = tuple(
        line.strip() for line in source.splitlines() if line.startswith("   ")
    )
    # Then: the page is reachable once, without a duplicate chapter.
    assert entries.count(page) == 1


def test_learning_routes_when_entering_docs_are_discoverable() -> None:
    # Given: the two public entry points and the shared route guide.
    landing = (_ROOT / "docs/index.rst").read_text(encoding="utf-8")
    readme = (_ROOT / "README.md").read_text(encoding="utf-8")
    # When: the welcome links and route headings are read.
    routes = (_ROOT / "docs/explanation/learning-paths.rst").read_text(encoding="utf-8")
    # Then: both entry points lead to beginner, practitioner and deep-dive routes.
    assert ":doc:`explanation/learning-paths`" in landing
    assert "(docs/explanation/learning-paths.rst)" in readme
    assert all(name in routes for name in ("Beginner", "Practitioner", "Deep dive"))
    assert f"<{_BLOB_PREFIX}examples/README.md>" in routes


def test_documentation_scope_preserves_cli_only_setup_and_explicit_commands() -> None:
    # Given: the public curriculum index.
    index = (_ROOT / "examples/README.md").read_text(encoding="utf-8")

    # When: the documented setup and per-lesson commands are inspected.
    required_commands = tuple(
        command
        for notebook in EXAMPLE_NOTEBOOKS
        for command in (
            f"just notebook-edit examples/{notebook.name}",
            f"just notebook-run examples/{notebook.name}",
            f"just notebook-script examples/{notebook.name}",
        )
    )

    # Then: a contributor can set up, author, consume, or script every lesson.
    assert "just sync" in index
    assert all(command in index for command in required_commands)


def test_validate_repository_course_reports_a_missing_index_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a complete temporary course whose index omits the final lesson.
    lessons = tuple(tmp_path / notebook.name for notebook in EXAMPLE_NOTEBOOKS)
    for lesson in lessons:
        _ = lesson.write_text("import marimo\n", encoding="utf-8")
    linked_lessons = lessons[:-1]
    _ = (tmp_path / "README.md").write_text(
        "\n".join(f"[{lesson.name}]({lesson.name})" for lesson in linked_lessons),
        encoding="utf-8",
    )
    monkeypatch.setattr(examples_check, "_EXAMPLES_DIRECTORY", tmp_path)
    monkeypatch.setattr(examples_check, "EXAMPLE_NOTEBOOKS", lessons)

    # When: the shared validator inspects the incomplete public index.
    with pytest.raises(
        AssertionError,
        match=r"curriculum index must link 10-comparative-methods\.py",
    ):
        examples_check.validate_repository_course()

    # Then: the missing entry is identified rather than silently accepted.


@pytest.mark.parametrize("lesson_path", EXAMPLE_NOTEBOOKS)
def test_no_metadata_or_blanket_lesson_suppressions(lesson_path: Path) -> None:
    # Given: one canonical Marimo lesson.

    # When: its source is read.
    source = lesson_path.read_text(encoding="utf-8")

    # Then: dependency metadata remains in the optional project group and
    # framework cells cannot bypass the repository's strict analysis settings.
    assert "# /// script" not in source
    assert "# pyright: basic" not in source
    assert "# ruff: noqa:" not in source


@pytest.mark.parametrize("lesson_path", _LESSON_PATHS)
def test_canonical_lessons_have_no_linter_or_type_checker_ignores(
    lesson_path: Path,
) -> None:
    # Given: one canonical numbered lesson.

    # When: its source is read.
    source = lesson_path.read_text(encoding="utf-8")

    # Then: it contains no local linter or type-checker suppression directives.
    assert "# noqa" not in source
    assert "# pyright: ignore" not in source
    assert "# type: ignore" not in source
