from __future__ import annotations

import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING, Final

from examples._support import run_local_command

if TYPE_CHECKING:
    from subprocess import CompletedProcess

_ROOT: Final = Path(__file__).resolve().parents[1]
_EXAMPLES_DIRECTORY: Final = _ROOT / "examples"
_EXPECTED_NOTEBOOK_NAMES: Final = (
    "01-overview.py",
    "02-collect.py",
    "03-summarize.py",
    "04-compare.py",
    "05-failures-and-ci.py",
)
EXAMPLE_NOTEBOOKS: Final[tuple[Path, ...]] = (
    *(_EXAMPLES_DIRECTORY / name for name in _EXPECTED_NOTEBOOK_NAMES),
)


def validate_repository_course() -> None:
    """Validate that the repository has all and only the canonical lessons."""
    assert (
        tuple(notebook.name for notebook in EXAMPLE_NOTEBOOKS)
        == _EXPECTED_NOTEBOOK_NAMES
    ), "course tuple must contain exactly the five canonical lessons"
    assert all(notebook.is_file() for notebook in EXAMPLE_NOTEBOOKS), (
        "every canonical lesson must exist"
    )
    numbered_notebook_names = {
        candidate.name
        for candidate in _EXAMPLES_DIRECTORY.iterdir()
        if candidate.is_file()
        and re.fullmatch(r"[0-9]{2}-.*\.py", candidate.name) is not None
    }
    assert numbered_notebook_names == set(_EXPECTED_NOTEBOOK_NAMES), (
        "examples must contain all and only the canonical numbered lessons"
    )
    index = (_EXAMPLES_DIRECTORY / "README.md").read_text(encoding="utf-8")
    for notebook in EXAMPLE_NOTEBOOKS:
        assert index.count(f"[{notebook.name}]({notebook.name})") == 1, (
            f"curriculum index must link {notebook.name} exactly once"
        )
        assert "# /// script" not in notebook.read_text(encoding="utf-8"), (
            f"{notebook.name} must not declare inline script metadata"
        )


def run_standalone_notebook(notebook: Path) -> CompletedProcess[str]:
    """Run one lesson with a temporary working directory that is removed afterward."""
    with TemporaryDirectory(prefix="perfcheck-example-run-") as directory:
        workspace = Path(directory)
        result = run_local_command(
            (
                "uv",
                "--directory",
                str(_ROOT),
                "run",
                "--group",
                "examples",
                "python",
                str(notebook.resolve()),
            ),
            cwd=workspace,
            timeout_seconds=15.0,
        )
    assert not workspace.exists()
    return result


def run_examples_check(notebooks: tuple[Path, ...]) -> int:
    """Run Marimo checks for exactly the notebooks supplied by the caller."""
    exit_code = 0
    for notebook in notebooks:
        with TemporaryDirectory(prefix="perfcheck-example-check-") as directory:
            workspace = Path(directory)
            result = run_local_command(
                (
                    "uv",
                    "--directory",
                    str(_ROOT),
                    "run",
                    "--group",
                    "examples",
                    "python",
                    "-m",
                    "marimo",
                    "check",
                    str(notebook.resolve()),
                ),
                cwd=workspace,
            )
        assert not workspace.exists()
        if exit_code == 0 and result.returncode != 0:
            exit_code = result.returncode
    return exit_code


def main() -> None:
    """Validate the fixed course and exit for its Marimo check result."""
    validate_repository_course()
    exit_code = run_examples_check(EXAMPLE_NOTEBOOKS)
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
