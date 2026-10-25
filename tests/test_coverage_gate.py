from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import ClassVar, Final

import pytest
from coverage import CoverageData
from pydantic import BaseModel, ConfigDict

_ROOT: Final = Path(__file__).parents[1]


class _Totals(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore", strict=True, frozen=True
    )
    num_statements: int
    covered_lines: int
    num_branches: int
    covered_branches: int
    percent_covered: float


class _Report(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="ignore", strict=True, frozen=True
    )
    totals: _Totals


def _project(root: Path, statements: int = 100) -> None:
    """Build a real pytest-cov project using the installed locked interpreter."""
    gate = _ROOT / "tools/coverage_gate.py"
    assert gate.is_file(), "the fresh coverage gate must exist"
    (root / "tools").mkdir()
    _ = shutil.copy2(gate, root / "tools/coverage_gate.py")
    _ = (root / "tools/__init__.py").write_text("", encoding="utf-8")
    recipe = (_ROOT / "justfile").read_text(encoding="utf-8")
    coverage_recipe = recipe[recipe.index('[env("COVERAGE_RCFILE"') :]
    coverage_recipe = coverage_recipe[: coverage_recipe.index("\n\n")]
    python = f'"{Path(sys.executable).as_posix()}"'
    coverage_recipe = coverage_recipe.replace("uv run pytest", f"{python} -m pytest")
    _ = (root / "justfile").write_text(
        coverage_recipe + f"\n\ncoverage-check:\n  {python} -m tools.coverage_gate\n",
        encoding="utf-8",
    )
    (root / "src/perfcheck").mkdir(parents=True)
    _ = (root / "src/perfcheck/__init__.py").write_text("", encoding="utf-8")
    # One unexecuted return, plus an executed branch, makes exact combined counts.
    _ = (root / "src/perfcheck/sample.py").write_text(
        """def missed():
    return 0
def branch(value):
    if value:
        return 1
    return 2
"""
        + "\n".join(f"value_{i} = {i}" for i in range(statements - 6))
        + "\n",
        encoding="utf-8",
    )
    (root / "tests").mkdir()
    _ = (root / "tests/test_sample.py").write_text(
        """from src.perfcheck import sample
def test_sample():
    assert sample.branch(True) == 1
    assert sample.branch(False) == 2
""",
        encoding="utf-8",
    )
    config = (_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    _ = (root / "pyproject.toml").write_text(
        config[config.index("[tool.coverage.run]") :], encoding="utf-8"
    )
    (root / "coverage/html").mkdir(parents=True)
    for name in ("html/index.html", "coverage.json", ".coverage", ".coverage.old"):
        _ = (root / "coverage" / name).write_text("STALE", encoding="utf-8")
    _ = (root / "coverage/keep.txt").write_text("unowned", encoding="utf-8")


def _run(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run the real recipe without inheriting the parent measurement session."""
    just = shutil.which("just")
    assert just is not None
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("COVERAGE_", "COV_CORE_", "_COVERAGE_", "PYTEST_"))
        or key == "PYTEST_ADDOPTS"
    }
    return subprocess.run(  # noqa: S603
        (just, "coverage-check", *args),
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


@pytest.mark.parametrize(
    ("statements", "expected_status"), [(48, 1), (98, 0), (198, 0), (78, 0)]
)
def test_gate_uses_combined_counts_and_installed_precision(
    tmp_path: Path, statements: int, expected_status: int
) -> None:
    # Given: one missed statement and two covered branches; 98.75 rounds to 99.
    _project(tmp_path, statements)

    # When: the fixed gate measures the whole isolated suite.
    result = _run(tmp_path)

    # Then: fail-under follows installed precision, not separate percent averages.
    assert result.returncode == expected_status, result.stdout + result.stderr
    totals = _Report.model_validate_json(
        (tmp_path / "coverage/coverage.json").read_bytes()
    ).totals
    assert totals.num_statements == statements
    assert totals.covered_lines == statements - 1
    assert totals.num_branches == totals.covered_branches == 2
    combined_percent = 100 * (statements + 1) / (statements + 2)
    assert totals.percent_covered == pytest.approx(combined_percent)
    assert "Coverage report" in (tmp_path / "coverage/html/index.html").read_text()
    data = CoverageData(basename=str(tmp_path / "coverage/.coverage"))
    data.read()
    assert data.has_arcs()
    assert not (tmp_path / "coverage/.coverage.old").exists()
    assert (tmp_path / "coverage/keep.txt").read_text() == "unowned"


def test_gate_preserves_completed_test_failure_and_fresh_reports(
    tmp_path: Path,
) -> None:
    # Given: adequate coverage but a genuine failing assertion and stale reports.
    _project(tmp_path, 198)
    with (tmp_path / "tests/test_sample.py").open("a", encoding="utf-8") as stream:
        _ = stream.write("    assert False, 'deliberate failure'\n")

    # When: tests complete unsuccessfully.
    result = _run(tmp_path)

    # Then: coverage success cannot mask pytest failure; fresh evidence survives.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "deliberate failure" in result.stdout
    report = _Report.model_validate_json(
        (tmp_path / "coverage/coverage.json").read_bytes()
    )
    assert report.totals.percent_covered > 99
    assert (tmp_path / "coverage/.coverage").read_bytes().startswith(b"SQLite format 3")
    assert "STALE" not in (tmp_path / "coverage/html/index.html").read_text()


@pytest.mark.parametrize("broken_file", ["tests/test_sample.py", "pyproject.toml"])
def test_gate_removes_old_evidence_before_early_failure(
    tmp_path: Path, broken_file: str
) -> None:
    # Given: invalid collection/configuration and preseeded old evidence.
    _project(tmp_path)
    _ = (tmp_path / broken_file).write_text("this is invalid !!!", encoding="utf-8")

    # When: execution fails before completing tests.
    result = _run(tmp_path)

    # Then: failure cannot expose stale success (new partial data may exist).
    assert result.returncode != 0
    for name in ("html/index.html", "coverage.json", ".coverage", ".coverage.old"):
        path = tmp_path / "coverage" / name
        assert not path.exists() or b"STALE" not in path.read_bytes()


@pytest.mark.parametrize(
    "output",
    [
        "coverage",
        "coverage/html",
        "coverage/html/index.html",
        "coverage/coverage.json",
        "coverage/.coverage",
        "coverage/.coverage.old",
    ],
)
def test_gate_refuses_symlink_outputs_without_external_deletion(
    tmp_path: Path, output: str
) -> None:
    # Given: a substituted output symlink to valuable external contents.
    root = tmp_path / "project"
    root.mkdir()
    _project(root)
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "keep.txt"
    _ = sentinel.write_text("valuable", encoding="utf-8")
    target = root / output
    directory = target.is_dir()
    if directory:
        shutil.rmtree(target)
    else:
        target.unlink()
    try:
        target.symlink_to(
            outside if directory else sentinel, target_is_directory=directory
        )
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    # When: the gate preflights its owned output paths.
    result = _run(root)

    # Then: it refuses before pytest, never traversing or writing the link.
    assert result.returncode != 0
    assert "symlink" in result.stderr.lower()
    assert sentinel.read_text() == "valuable"
    assert target.is_symlink()


@pytest.mark.parametrize("argument", ["tests/test_sample.py", "--cov-fail-under=0"])
def test_gate_recipe_rejects_selection_and_threshold_arguments(
    tmp_path: Path, argument: str
) -> None:
    # Given: a zero-argument recipe and an attempted override.
    _project(tmp_path)

    # When: the caller attempts to weaken the fixed command.
    result = _run(tmp_path, argument)

    # Then: Just refuses before cleanup or execution.
    assert result.returncode != 0
    assert (tmp_path / "coverage/coverage.json").read_text() == "STALE"


def test_gate_ignores_environment_selection_and_threshold_overrides(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a below-threshold project and environment arguments hiding its test.
    _project(tmp_path, 48)
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k nonexistent --cov-fail-under=0")

    # When: the fixed gate runs without accepting user selection.
    result = _run(tmp_path)

    # Then: the full test executes and the fixed threshold fails.
    assert result.returncode == 1, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert "Required test coverage of 99% not reached" in result.stdout


def test_repository_gate_recipe_invokes_the_zero_argument_tool() -> None:
    # Given: the actual recipe rather than the isolated fixture wiring.
    just = shutil.which("just")
    assert just is not None

    # When: Just renders its gate command.
    result = subprocess.run(  # noqa: S603
        (just, "--dry-run", "coverage-check"),
        cwd=_ROOT,
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )

    # Then: only the fixed tool is invoked, with no argument forwarding.
    assert result.returncode == 0
    assert result.stderr.strip() == "uv run python -m tools.coverage_gate"
