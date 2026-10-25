import re
import tomllib
from pathlib import Path
from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict, Field
from tools.mutation_runner import snapshot


class MutationConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    source_paths: list[str]
    only_mutate: list[str]
    pytest_add_cli_args_test_selection: list[str]
    max_stack_depth: int
    type_check_command: list[str]
    mutate_only_covered_lines: bool
    timeout_multiplier: int
    timeout_constant: int
    pytest_add_cli_args: list[str]
    do_not_mutate_patterns: list[str] = Field(default_factory=list)


class ToolConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    mutmut: MutationConfig


class ProjectConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)
    tool: ToolConfig


def test_mutation_is_explicit_and_targeted() -> None:
    # Given: the repository's opt-in command and dependency configuration.
    root = Path(__file__).parents[1]
    config = ProjectConfig.model_validate(
        tomllib.loads((root / "pyproject.toml").read_text())
    )
    # When: the mutation configuration is inspected.
    mutation = config.tool.mutmut
    # Then: only the aggregation target and selected tests participate.
    assert mutation.source_paths == ["src/"]
    assert mutation.only_mutate == ["src/perfcheck/regression_aggregation.py"]
    assert mutation.pytest_add_cli_args_test_selection == [
        "tests/test_suite_aggregation.py"
    ]
    assert mutation.max_stack_depth == -1
    assert mutation.type_check_command == []
    assert not mutation.mutate_only_covered_lines
    assert mutation.timeout_multiplier == 15
    assert mutation.timeout_constant == 1
    assert mutation.pytest_add_cli_args == [
        "-p",
        "no:pytest_cov",
        "-p",
        "tools.mutation_probe",
    ]
    assert (
        "\"mutmut==3.8.0; sys_platform != 'win32'\""
        in (root / "pyproject.toml").read_text()
    )


def test_ordinary_sync_excludes_mutation() -> None:
    # Given: the canonical Just recipes.
    recipes = (Path(__file__).parents[1] / "justfile").read_text()
    # When: the ordinary synchronization recipe is selected.
    sync = recipes.split("\nsync:\n", 1)[1]
    # Then: its explicit groups exclude optional mutation dependencies.
    assert "uv sync --locked --group dev --group docs --group examples" in sync
    assert "--all-groups" not in sync
    assert "--group mutation" not in sync


def test_only_standalone_assert_never_is_excluded() -> None:
    # Given: the parsed central mutation configuration, without optional mutmut.
    root = Path(__file__).parents[1]
    config = ProjectConfig.model_validate(
        tomllib.loads((root / "pyproject.toml").read_text())
    )
    # When: the native generator's exclusion patterns are selected.
    patterns = config.tool.mutmut.do_not_mutate_patterns
    # Then: no generic assert, case, raise or covered-line exclusion is added.
    assert patterns == [r"^[ \t]*assert_never\("]
    assert not config.tool.mutmut.mutate_only_covered_lines


@pytest.mark.parametrize(
    ("line", "excluded"),
    [
        ("assert_never(status)", True),
        ("        assert_never(metric.status)", True),
        ("\tassert_never(value)", True),
        ("    assert_never(None)", True),
        ("    case _:", False),
        ("    case Status.FAIL:", False),
        ("    assert enabled", False),
        ("    raise ValueError(value)", False),
        ("    if metric.enabled:", False),
        ("    return Status.FAIL", False),
        ("    typing.assert_never(value)", False),
        ("    result = assert_never(value)", False),
        ("    case _: assert_never(value)", False),
        ("    assert_never_extra(value)", False),
    ],
)
def test_mutation_exclusion_line_boundary(line: str, excluded: bool) -> None:
    # Given: ordinary code beside a standalone unqualified exhaustive guard.
    config = ProjectConfig.model_validate(
        tomllib.loads((Path(__file__).parents[1] / "pyproject.toml").read_text())
    )
    # When: the configured line filters are applied as regular expressions.
    matched = any(
        re.search(pattern, line)
        for pattern in config.tool.mutmut.do_not_mutate_patterns
    )
    # Then: meaningful sibling lines and qualified/embedded calls remain eligible.
    assert matched == excluded


def test_mutation_snapshot_preserves_central_exclusion(tmp_path: Path) -> None:
    # Given: the real runner's disposable snapshot of repository inputs.
    destination = tmp_path / "snapshot"
    # When: the existing snapshot boundary copies the central configuration.
    snapshot(Path(__file__).parents[1], destination)
    config = ProjectConfig.model_validate(
        tomllib.loads((destination / "pyproject.toml").read_text())
    )
    # Then: generation receives the rule, rather than filtering reported outcomes.
    assert config.tool.mutmut.do_not_mutate_patterns == [r"^[ \t]*assert_never\("]
