from __future__ import annotations

import re
import sys
from pathlib import Path
from subprocess import CompletedProcess
from typing import TYPE_CHECKING

import pytest

from tests import examples_check
from tests.examples_check import run_examples_check

if TYPE_CHECKING:
    from collections.abc import Sequence


_ROOT = Path(__file__).parents[1]


def test_example_notebook_tuple_covers_the_ten_canonical_lessons() -> None:
    # Given: the fixed course tuple consumed by the examples checker.

    # When: its lesson filenames are read in sequence.
    notebook_names = tuple(path.name for path in examples_check.EXAMPLE_NOTEBOOKS)

    # Then: it contains all and only the ten ordered curriculum lessons.
    assert notebook_names == (
        "01-overview.py",
        "02-collect.py",
        "03-summarize.py",
        "04-compare.py",
        "05-failures-and-ci.py",
        "06-statistical-foundations.py",
        "07-summary-and-eligibility.py",
        "08-bootstrap-and-decisions.py",
        "09-plain-python-mechanics.py",
        "10-comparative-methods.py",
    )


def test_validate_repository_course_rejects_a_noncanonical_lesson_tuple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the repository course with its final lesson omitted from the tuple.
    monkeypatch.setattr(
        examples_check,
        "EXAMPLE_NOTEBOOKS",
        examples_check.EXAMPLE_NOTEBOOKS[:-1],
    )

    # When: the checker validates the altered canonical tuple.

    # Then: it rejects the incomplete list before checking generated outputs.
    with pytest.raises(
        AssertionError,
        match="course tuple must contain exactly the ten canonical lessons",
    ):
        examples_check.validate_repository_course()


def test_run_examples_check_returns_nonzero_for_invalid_path(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: a temporary notebook with invalid Python syntax.
    invalid_path = tmp_path / "invalid-notebook.py"
    _ = invalid_path.write_text(
        """\
import marimo

app = marimo.App()


@app.cell
def _():
    x = 1
    global x


if __name__ == "__main__":
    app.run()
""",
        encoding="utf-8",
    )

    # When: the parameterized checker receives only that absolute notebook path.
    return_code = run_examples_check((invalid_path,))

    # Then: Marimo reports the invalid notebook with a nonzero process result.
    assert return_code != 0
    captured = capsys.readouterr()
    assert invalid_path.name in captured.err


def test_validate_repository_course_rejects_a_missing_lesson_command(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: an otherwise complete temporary course without one consumer command.
    lessons = tuple(tmp_path / path.name for path in examples_check.EXAMPLE_NOTEBOOKS)
    for lesson in lessons:
        _ = lesson.write_text("import marimo\n", encoding="utf-8")
    lines: list[str] = []
    for lesson in lessons:
        lines.extend(
            (
                f"[{lesson.name}]({lesson.name})",
                f"uv run --group examples marimo edit examples/{lesson.name}",
                f"uv --directory . run --group examples python examples/{lesson.name}",
            )
        )
        if lesson != lessons[-1]:
            lines.append(f"uv run --group examples marimo run examples/{lesson.name}")
    _ = (tmp_path / "README.md").write_text("\n".join(lines), encoding="utf-8")
    monkeypatch.setattr(examples_check, "_EXAMPLES_DIRECTORY", tmp_path)
    monkeypatch.setattr(examples_check, "EXAMPLE_NOTEBOOKS", lessons)

    # When: the examples checker validates the public course index.

    # Then: it identifies the omitted command for the final canonical lesson.
    with pytest.raises(
        AssertionError,
        match=(
            "curriculum index must include author, consumer, and script commands "
            f"for {re.escape(lessons[-1].name)}"
        ),
    ):
        examples_check.validate_repository_course()


def test_main_exits_for_examples_test_failure_after_marimo_validation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    # Given: successful course validation and a failing focused pytest child.
    calls: list[tuple[tuple[str, ...], Path, float]] = []

    def validate_course() -> None:
        return None

    def validate_notebooks(notebooks: tuple[Path, ...]) -> int:
        assert notebooks == examples_check.EXAMPLE_NOTEBOOKS
        return 0

    def run_focused_tests(
        arguments: Sequence[str], *, cwd: Path, timeout_seconds: float = 0.0
    ) -> CompletedProcess[str]:
        calls.append((tuple(arguments), cwd, timeout_seconds))
        return CompletedProcess(
            arguments, 7, stdout="FAILED mathematical oracle\n", stderr="child error\n"
        )

    monkeypatch.setattr(examples_check, "validate_repository_course", validate_course)
    monkeypatch.setattr(examples_check, "run_examples_check", validate_notebooks)
    monkeypatch.setattr(examples_check, "run_local_command", run_focused_tests)

    # When: the public examples entrypoint runs after Marimo validation.
    with pytest.raises(SystemExit) as error:
        examples_check.main()

    # Then: it runs all focused modules with the existing budget and shows errors.
    assert error.value.code == 7
    captured = capsys.readouterr()
    assert "FAILED mathematical oracle" in captured.err
    assert "child error" in captured.err
    assert calls == [
        (
            (
                sys.executable,
                "-m",
                "pytest",
                str(_ROOT / "tests/test_examples.py"),
                str(_ROOT / "tests/test_examples_support.py"),
                str(_ROOT / "tests/test_examples_fixture.py"),
                str(_ROOT / "tests/test_examples_workflow.py"),
                str(_ROOT / "tests/test_examples_check.py"),
                str(_ROOT / "tests/test_examples_mechanics.py"),
                str(_ROOT / "tests/test_examples_comparative.py"),
                str(_ROOT / "tests/test_examples_probability.py"),
                str(_ROOT / "tests/test_examples_design.py"),
                str(_ROOT / "tests/test_examples_inference.py"),
                str(_ROOT / "tests/test_examples_power.py"),
                str(_ROOT / "tests/test_examples_multiple_testing.py"),
            ),
            _ROOT,
            60.0,
        )
    ]
