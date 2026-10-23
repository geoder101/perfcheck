from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest
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
    }


def test_workflow_pages_document_only_supported_cli_contracts() -> None:
    # Given: the tutorial and task guides offered to CLI users.
    sources = tuple(_read(path) for path in _WORKFLOW_SOURCES)
    cli = _read(Path("src/perfcheck/cli.py"))

    # When: their required options and reported outcomes are checked.
    documented = "\n".join(sources)

    # Then: every workflow claim maps to the public command contract.
    required_options = (
        "--suite",
        "--run-id",
        "--start",
        "--end",
        "--out",
        "--policy",
        "--run",
        "--current",
        "--baseline",
        "--report-json",
        "--report-md",
        "--force",
        "--write-summary-cache",
    )
    assert all(option in documented and option in cli for option in required_options)
    assert "exit status ``0`` for ``PASS``" in documented
    assert "exit status ``1`` for ``FAIL``" in documented
    assert "exit status ``2`` for ``INCONCLUSIVE``" in documented
    assert "exit status ``3`` for invalid command input" in documented
    assert "exit status ``4``" in documented
    _assert_exit_claims(documented)


def test_workflow_pages_keep_diataxis_boundaries_and_safe_artifact_language() -> None:
    # Given: the rendered source for every new workflow document.
    sources = tuple(_read(path) for path in _WORKFLOW_SOURCES)

    # When: the documentation boundaries are inspected.

    # Then: each page has task structure, cross-links, and no stability promise.
    for source in sources:
        assert "Goal" in source
        assert "Prerequisite" in source
        assert "Steps" in source
        assert "Expected observable" in source
        assert ":doc:`" in source
    documented = "\n".join(sources).lower()
    assert "stable artifact" not in documented
    assert "python api" not in documented


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
        for match in re.finditer(r"(?<![\w-])--[a-z][a-z0-9-]*", help_output)
    }
    assert set(options) <= live_options


@pytest.mark.parametrize("command", ["collect", "summarize", "compare"])
def test_reference_options_exist_in_live_command_help(command: str) -> None:
    # Given: the Reference section for one supported CLI command.
    reference = _read(Path("docs/reference/cli.rst"))
    section = reference.split(f"\n``{command}``\n", maxsplit=1)[1]
    section = re.split(r"\n(?:``\w+``|Exit outcomes)\n", section, maxsplit=1)[0]

    # When: the real Typer application renders that command's installed help.
    result = CliRunner().invoke(app, [command, "--help"], color=False)

    # Then: every documented option belongs to a live, successful command.
    assert result.exit_code == 0
    _assert_documented_options(section, result.output)


def test_reference_options_reject_a_nonexistent_live_option_prefix() -> None:
    # Given: real Reference prose that shortens --report-json to nonexistent --report.
    reference = _read(Path("docs/reference/cli.rst"))
    section = reference.split("\n``compare``\n", maxsplit=1)[1].replace(
        "``--report-json``", "``--report``"
    )
    result = CliRunner().invoke(app, ["compare", "--help"], color=False)
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
    options = result.stdout.split("Options", maxsplit=1)[1]
    description = options.split("--json", maxsplit=1)[1].split("--help", maxsplit=1)[0]
    normalized = " ".join(description.replace("│", " ").split())
    assert "Additionally emit the JSON report to stdout" in normalized
    assert "--report-json or --report-md is still required" in normalized


def test_compare_guide_shows_json_stdout_capture_with_a_markdown_report() -> None:
    # Given: the task guide for comparing current and baseline evidence.
    source = _read(Path("docs/how-to/compare-cohorts.rst"))

    # When: its console examples are inspected.
    commands = re.findall(r"^\s+\$ (.+)$", source, re.MULTILINE)

    # Then: one example captures JSON stdout while requesting a Markdown file.
    assert (
        "uv run perfcheck compare --policy policy.json "
        "--current summaries/current-1.json --baseline summaries/baseline-1.json "
        "--report-md reports/comparison.md --json > reports/comparison.json"
    ) in commands
