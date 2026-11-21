from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
from click import unstyle
from typer.testing import CliRunner

from perfcheck.cli import app

_ROOT: Final = Path(__file__).parents[1]
_WORKFLOW_SOURCES: Final = (
    Path("docs/tutorials/first-comparison.rst"),
    Path("docs/how-to/collect-a-run.rst"),
    Path("docs/how-to/summarize-evidence.rst"),
    Path("docs/how-to/compare-cohorts.rst"),
    Path("docs/how-to/ci-regression-gate.rst"),
)


def _read(relative_path: Path) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_exit_claims(documented: str) -> None:
    claims = set(
        re.findall(
            r"exit status ``(\d+)``(?: for ``([^`]+)``)?",
            " ".join(documented.split()),
            re.IGNORECASE,
        )
    )
    assert claims == {
        ("0", "PASS"),
        ("1", "FAIL"),
        ("2", "INCONCLUSIVE"),
        ("3", ""),
        ("4", ""),
        ("5", "internal failure"),
    }


@pytest.mark.parametrize("replacement", ["5", "0"])
def test_workflow_docs_reject_an_invented_exit_claim(replacement: str) -> None:
    # Given: the real guides with the inconclusive exit changed to success or unknown.
    documented = "\n".join(_read(path) for path in _WORKFLOW_SOURCES).replace(
        "exit status ``2``", f"exit status ``{replacement}``"
    )

    # When: a made-up CLI outcome is introduced.

    # Then: the public exit-code contract rejects it.
    with pytest.raises(AssertionError):
        _assert_exit_claims(documented)


def _assert_documented_options(section: str, help_output: str) -> None:
    options = tuple(
        match.group(1) for match in re.finditer(r"``(--[a-z-]+)``", section)
    )
    assert options
    live_options = {
        match.group()
        for match in re.finditer(r"(?<![\w-])--[a-z][a-z0-9-]*", unstyle(help_output))
    }
    assert set(options) <= live_options


@pytest.mark.parametrize("command", ["collect", "summarize", "compare"])
def test_reference_options_exist_in_live_command_help(command: str) -> None:
    # Given: the Reference section for one supported CLI command.
    reference = _read(Path("docs/reference/cli.rst"))
    section = reference.split(f"\n``{command}``\n", maxsplit=1)[1]
    section = re.split(r"\n(?:``\w+``|Exit outcomes)\n", section, maxsplit=1)[0]

    # When: render at a wide width so Rich keeps full option names for exact match.
    result = CliRunner().invoke(
        app, [command, "--help"], color=False, env={"COLUMNS": "200"}
    )

    # Then: every documented option belongs to a live, successful command.
    assert result.exit_code == 0
    _assert_documented_options(section, result.output)


def test_reference_options_reject_a_nonexistent_live_option_prefix() -> None:
    # Given: real Reference prose that shortens --report-json to nonexistent --report.
    reference = _read(Path("docs/reference/cli.rst"))
    section = reference.split("\n``compare``\n", maxsplit=1)[1].replace(
        "``--report-json``", "``--report``"
    )
    result = CliRunner().invoke(
        app, ["compare", "--help"], color=False, env={"COLUMNS": "200"}
    )
    assert result.exit_code == 0

    # When: the same live-option validator checks the misleading prose.
    # Then: an option prefix cannot masquerade as a complete supported flag.
    with pytest.raises(AssertionError):
        _assert_documented_options(section, result.output)


def test_compare_json_option_help_explains_additional_stdout_output() -> None:
    # Given: the public compare command with its explicit JSON stdout flag.
    # When: users request option-level help.
    result = CliRunner().invoke(app, ["compare", "--help"], color=False)

    # Then: the JSON option itself explains stdout and the report-file requirement.
    assert result.exit_code == 0
    options = unstyle(result.stdout).split("Options", maxsplit=1)[1]
    description = options.split("--json", maxsplit=1)[1].split("--help", maxsplit=1)[0]
    normalized = " ".join(description.replace("│", " ").split())
    assert "Additionally emit the JSON report to stdout" in normalized
    assert "--report-json or --report-md is still required" in normalized
