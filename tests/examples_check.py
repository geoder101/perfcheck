from __future__ import annotations

import re
import sys
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
    "06-statistical-foundations.py",
    "07-summary-and-eligibility.py",
    "08-bootstrap-and-decisions.py",
    "09-plain-python-mechanics.py",
    "10-comparative-methods.py",
)
_EXAMPLES_TEST_TIMEOUT_SECONDS: Final = 60.0
EXAMPLE_NOTEBOOKS: Final[tuple[Path, ...]] = (
    *(_EXAMPLES_DIRECTORY / name for name in _EXPECTED_NOTEBOOK_NAMES),
)


def validate_repository_course() -> None:
    """Validate that the repository has all and only the canonical lessons."""
    assert (
        tuple(notebook.name for notebook in EXAMPLE_NOTEBOOKS)
        == _EXPECTED_NOTEBOOK_NAMES
    ), "course tuple must contain exactly the ten canonical lessons"
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
    for notebook in EXAMPLE_NOTEBOOKS:
        commands = (
            f"uv run --group examples marimo edit examples/{notebook.name}",
            f"uv run --group examples marimo run examples/{notebook.name}",
            f"uv --directory . run --group examples python examples/{notebook.name}",
        )
        assert all(command in index for command in commands), (
            "curriculum index must include author, consumer, and script commands "
            f"for {notebook.name}"
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
        if result.returncode != 0:
            _ = sys.stderr.write(
                f"Marimo check failed: {notebook}\n{result.stdout}{result.stderr}"
            )
        if exit_code == 0 and result.returncode != 0:
            exit_code = result.returncode
    return exit_code


def main() -> None:
    """Validate the fixed course and run all optional examples checks."""
    validate_repository_course()
    exit_code = run_examples_check(EXAMPLE_NOTEBOOKS)
    test_result = run_local_command(
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
        cwd=_ROOT,
        timeout_seconds=_EXAMPLES_TEST_TIMEOUT_SECONDS,
    )
    if test_result.returncode != 0:
        _ = sys.stderr.write(
            f"Focused examples tests failed:\n{test_result.stdout}{test_result.stderr}"
        )
    if exit_code == 0:
        exit_code = test_result.returncode
    if exit_code != 0:
        raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
