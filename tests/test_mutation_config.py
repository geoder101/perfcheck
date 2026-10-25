import tomllib
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict


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
