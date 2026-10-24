from __future__ import annotations

import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from pydantic import JsonValue, TypeAdapter

_ROOT = Path(__file__).parents[1]


def test_coverage_measures_only_application_branches_and_subprocesses() -> None:
    # Given: the repository's shared tool configuration.
    configuration = TypeAdapter(dict[str, JsonValue]).validate_python(
        tomllib.loads((_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    )

    # When: the coverage run settings are inspected semantically.
    tool = configuration["tool"]
    assert isinstance(tool, dict)
    coverage = tool.get("coverage")
    assert isinstance(coverage, dict)
    run = coverage["run"]

    # Then: only application branches and child processes are requested.
    assert isinstance(run, dict)
    assert run["branch"] is True
    assert run["source"] == ["src/perfcheck"]
    assert run["patch"] == ["subprocess"]
    assert "dynamic_context" not in run
    report = coverage.get("report", {})
    assert isinstance(report, dict)
    assert report.get("fail_under", 0) == 0
    assert "exclude_lines" not in report
    assert report.get("exclude_also") == [
        r"(?m:^[ \t]*case _:[ \t]*\r?\n[ \t]+assert_never\()"
    ]


def test_coverage_recipe_preserves_test_selection_and_requests_reports() -> None:
    # Given: Just can render commands without executing pytest.
    just = shutil.which("just")
    assert just is not None

    # When: a selected coverage run is rendered with an extra pytest argument.
    result = subprocess.run(  # noqa: S603
        (just, "--dry-run", "coverage", "tests/test_coverage_config.py"),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    # Then: coverage is opt-in, forwards selection, and writes all three reports.
    assert result.returncode == 0, result.stderr
    tokens = shlex.split(result.stderr)
    assert "--cov" in tokens
    assert "--cov-report=term-missing" in tokens
    assert "--cov-report=html" in tokens
    assert "--cov-report=json" in tokens
    assert "--ignore=tests/test_examples.py" in tokens
    assert "--ignore=tests/test_examples_check.py" in tokens
    assert "tests/test_coverage_config.py" in tokens
    assert f"--cov-config={_ROOT / 'pyproject.toml'}" in tokens


@pytest.mark.parametrize("recipe", ["test", "check"])
def test_ordinary_recipes_keep_coverage_opt_in(recipe: str) -> None:
    # Given: the ordinary developer recipes.
    just = shutil.which("just")
    assert just is not None

    # When: Just renders the recipe's effective command graph.
    result = subprocess.run(  # noqa: S603
        (just, "--dry-run", recipe),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )

    # Then: measurement is never enabled by the standard gates.
    assert "--cov" not in result.stderr
    assert "COVERAGE_" not in result.stderr
