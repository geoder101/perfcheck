from __future__ import annotations

import ast
from pathlib import Path

import pytest
from coverage import Coverage
from pydantic import BaseModel

_ROOT = Path(__file__).parents[1]


class Region(BaseModel, frozen=True):
    excluded_lines: tuple[int, ...]
    missing_lines: tuple[int, ...]
    missing_branches: tuple[tuple[int, int], ...]


class FileReport(Region, frozen=True):
    functions: dict[str, Region]


class Report(BaseModel, frozen=True):
    files: dict[str, FileReport]


@pytest.fixture
def reports(tmp_path: Path, newline: str) -> tuple[FileReport, FileReport]:
    source = (_ROOT / "tests/coverage_cases.py").read_text(encoding="utf-8")
    module = tmp_path / "coverage_cases.py"
    _ = module.write_bytes(source.replace("\n", newline).encode())
    results: list[FileReport] = []
    for config in (False, str(_ROOT / "pyproject.toml")):
        coverage = Coverage(
            config_file=config,
            data_file=str(tmp_path / f"data-{len(results)}"),
            branch=True,
        )
        coverage.set_option("run:source", [str(tmp_path)])
        # Analysis only: empty branch data avoids replacing pytest-cov's tracer.
        coverage.get_data().add_arcs({str(module): []})
        output = tmp_path / f"report-{len(results)}.json"
        _ = coverage.json_report(morfs=[str(module)], outfile=str(output))
        report = Report.model_validate_json(output.read_bytes())
        results.append(next(iter(report.files.values())))
    return results[0], results[1]


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_exhaustive_guard_excludes_statements_and_branches(
    reports: tuple[FileReport, FileReport],
) -> None:
    # Given: identical unexecuted source analyzed with defaults and project config.
    original, configured = reports
    before = original.functions["exhaustive"]
    tree = ast.parse((_ROOT / "tests/coverage_cases.py").read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "exhaustive"
    )
    statement = function.body[0]
    assert isinstance(statement, ast.Match)
    first, second, wildcard = statement.cases
    guard_lines = {wildcard.pattern.lineno, wildcard.body[0].lineno}
    surviving_arcs = {
        (first.pattern.lineno, first.body[0].lineno),
        (first.pattern.lineno, second.pattern.lineno),
    }

    # When: the exhaustive wildcard's reporting region is inspected.
    after = configured.functions["exhaustive"]

    # Then: only the wildcard and guard leave both missing lines and branch arcs.
    excluded = set(after.excluded_lines) - set(before.excluded_lines)
    assert excluded == guard_lines
    assert set(after.missing_lines) == set(before.missing_lines) - guard_lines
    assert set(after.missing_branches) == surviving_arcs
    assert set(before.missing_branches) == surviving_arcs | {
        (second.pattern.lineno, second.body[0].lineno),
        (second.pattern.lineno, wildcard.pattern.lineno),
    }


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_meaningful_fallback_and_validation_remain_missing(
    reports: tuple[FileReport, FileReport],
) -> None:
    # Given: ordinary wildcard returns and validation raises were never executed.
    original, configured = reports

    # When: their reporting regions are compared.
    for name in ("fallback", "validate"):
        before = original.functions[name]
        after = configured.functions[name]

        # Then: all statements and both branch destinations remain measurable.
        assert after == before
        assert after.missing_lines
        assert len(after.missing_branches) == 2
        assert after.excluded_lines == ()


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
def test_default_pragma_exclusion_is_preserved(
    reports: tuple[FileReport, FileReport],
) -> None:
    # Given: a default pragma exclusion alongside the new project rule.
    original, configured = reports

    # When: the pragma-controlled region is inspected.
    before = original.functions["default_pragma"]
    after = configured.functions["default_pragma"]

    # Then: default exclusions still remove the clause and its branch choice.
    assert after == before
    assert len(after.excluded_lines) == 2
    assert after.missing_branches == ()


def test_production_wildcard_guards_have_no_other_fallback_behavior() -> None:
    # Given: all production matches, including future additions.
    paths = sorted((_ROOT / "src/perfcheck").rglob("*.py"))
    guards: list[ast.match_case] = []

    # When: a wildcard suite starts with assert_never.
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.match_case):
                continue
            match node:
                case ast.match_case(
                    pattern=ast.MatchAs(pattern=None, name=None),
                    body=[
                        ast.Expr(value=ast.Call(func=ast.Name(id="assert_never"))),
                        *_,
                    ],
                ):
                    # Then: exclusion cannot hide adjacent meaningful fallback code.
                    assert node.guard is None, path
                    assert len(node.body) == 1, path
                    guards.append(node)
                case _:
                    continue
    assert guards
