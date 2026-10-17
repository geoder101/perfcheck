from __future__ import annotations

from typing import TYPE_CHECKING

from tests.examples_check import run_examples_check

if TYPE_CHECKING:
    from pathlib import Path


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
