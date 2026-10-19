from __future__ import annotations

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


def test_run_examples_check_returns_nonzero_for_invalid_path(
    tmp_path: Path,
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


def test_main_exits_for_examples_test_failure_after_marimo_validation(
    monkeypatch: pytest.MonkeyPatch,
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
        return CompletedProcess(arguments, 7, stdout="", stderr="")

    monkeypatch.setattr(examples_check, "validate_repository_course", validate_course)
    monkeypatch.setattr(examples_check, "run_examples_check", validate_notebooks)
    monkeypatch.setattr(examples_check, "run_local_command", run_focused_tests)

    # When: the public examples entrypoint runs after Marimo validation.
    with pytest.raises(SystemExit) as error:
        examples_check.main()

    # Then: it runs both optional modules through the managed Python and fails.
    assert error.value.code == 7
    assert calls == [
        (
            (
                sys.executable,
                "-m",
                "pytest",
                str(_ROOT / "tests/test_examples.py"),
                str(_ROOT / "tests/test_examples_check.py"),
            ),
            _ROOT,
            60.0,
        )
    ]
