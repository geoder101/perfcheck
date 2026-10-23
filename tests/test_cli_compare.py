from pathlib import Path  # noqa: TC003 - pytest resolves fixture annotations.

import pytest
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.cli_services import load_raw
from perfcheck.report_schemas import Report
from perfcheck.storage import summary_cache_path
from tests.cli_support import (
    SummaryInputKind,
    compare_inputs,
    rejected_summary_input,
    write_cli_summary,
)


@pytest.fixture
def compare_arguments(tmp_path: Path) -> list[str]:
    return compare_inputs(tmp_path)


@pytest.mark.parametrize("formats", [("json",), ("md",), ("json", "md")])
@pytest.mark.parametrize("emit_json", [False, True])
def test_compare_writes_only_requested_reports(
    tmp_path: Path,
    compare_arguments: list[str],
    formats: tuple[str, ...],
    emit_json: bool,
) -> None:
    # Given: valid evidence and one or both explicit report destinations.
    arguments = list(compare_arguments)
    for format_name in formats:
        arguments.extend(
            [f"--report-{format_name}", str(tmp_path / f"report.{format_name}")]
        )
    if emit_json:
        arguments.append("--json")

    # When: the comparison runs with the selected outputs.
    result = CliRunner().invoke(app, arguments)

    # Then: the verdict is unchanged and omitted formats have no default output.
    assert result.exit_code == 2
    assert {path.name for path in tmp_path.glob("report.*")} == {
        f"report.{format_name}" for format_name in formats
    }
    if "json" in formats:
        report = Report.model_validate_json((tmp_path / "report.json").read_bytes())
        assert report.suite_status == "inconclusive"
    if "md" in formats:
        assert "inconclusive" in (tmp_path / "report.md").read_text(encoding="utf-8")
    if emit_json:
        assert Report.model_validate_json(result.stdout).suite_status == "inconclusive"
        if "json" in formats:
            assert result.stdout == (tmp_path / "report.json").read_text(
                encoding="utf-8"
            )
    else:
        assert result.stdout == ""


@pytest.mark.parametrize("emit_json", [False, True])
def test_compare_requires_a_report_file_before_loading_inputs(
    tmp_path: Path, emit_json: bool
) -> None:
    # Given: no report output, missing inputs, and optional stdout emission.
    arguments = [
        "compare",
        "--policy",
        str(tmp_path / "missing-policy.json"),
        "--current",
        str(tmp_path / "current.json"),
        "--baseline",
        str(tmp_path / "baseline.json"),
        "--write-summary-cache",
    ]
    if emit_json:
        arguments.append("--json")

    # When: compare is invoked without either report option.
    result = CliRunner().invoke(app, arguments)

    # Then: stdout cannot substitute for a file, and no input or cache is touched.
    assert result.exit_code == 3
    assert "error:" in result.stderr
    assert "at least one of --report-json or --report-md is required" in result.stderr
    assert result.stdout == ""
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("format_name", ["json", "md"])
@pytest.mark.parametrize("force", [False, True])
def test_compare_preserves_overwrite_safety_for_individual_outputs(
    tmp_path: Path, compare_arguments: list[str], format_name: str, force: bool
) -> None:
    # Given: an existing requested output and an unrequested sibling with user data.
    output = tmp_path / f"report.{format_name}"
    sibling = tmp_path / ("report.md" if format_name == "json" else "report.json")
    _ = output.write_text("keep-requested", encoding="utf-8")
    _ = sibling.write_text("keep-omitted", encoding="utf-8")
    arguments = [*compare_arguments, f"--report-{format_name}", str(output)]
    if force:
        arguments.append("--force")

    # When: compare receives only the selected output, with replacement opt-in or not.
    result = CliRunner().invoke(app, arguments)

    # Then: only the explicit output is preflighted and eligible for replacement.
    assert result.exit_code == (2 if force else 3)
    assert sibling.read_text(encoding="utf-8") == "keep-omitted"
    if force:
        assert "inconclusive" in output.read_text(encoding="utf-8")
    else:
        assert output.read_text(encoding="utf-8") == "keep-requested"


@pytest.mark.parametrize(
    "kind", ["tampered", "other-policy", "corrupt-cache", "source-mismatch"]
)
@pytest.mark.parametrize("write_cache", [False, True])
def test_compare_rejects_invalid_summary_evidence_without_outputs(
    tmp_path: Path, kind: SummaryInputKind, write_cache: bool
) -> None:
    # Given: invalid direct evidence or an invalid existing sibling cache.
    arguments, evidence = rejected_summary_input(tmp_path, kind)
    original = evidence.read_bytes()
    if write_cache:
        arguments.append("--write-summary-cache")

    # When: compare requests both reports and JSON stdout.
    result = CliRunner().invoke(
        app,
        [
            *arguments,
            "--report-json",
            str(tmp_path / "report.json"),
            "--report-md",
            str(tmp_path / "report.md"),
            "--json",
        ],
    )

    # Then: sanitized refusal neither replaces bad evidence nor publishes reports.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert result.stderr == "error: invalid command input\n"
    assert "fixture-secret" not in result.stderr
    assert not list(tmp_path.glob("report.*"))
    assert evidence.read_bytes() == original


def test_compare_reuses_valid_caches_without_rewriting_them(
    tmp_path: Path, compare_arguments: list[str]
) -> None:
    # Given: valid sibling caches whose whitespace would change on serialization.
    caches: dict[Path, bytes] = {}
    for raw_path in (tmp_path / "current-0.json", tmp_path / "baseline-0.json"):
        raw = load_raw(raw_path)
        cache = summary_cache_path(raw_path, raw.policy_sha256)
        write_cli_summary(cache, raw)
        original = b"\n " + cache.read_bytes()
        _ = cache.write_bytes(original)
        caches[cache] = original
    report_path = tmp_path / "report.json"

    # When: raw convenience inputs are compared without cache-write permission.
    result = CliRunner().invoke(
        app, [*compare_arguments, "--report-json", str(report_path), "--json"]
    )

    # Then: both cache hits stay on stderr and stdout is exactly the JSON report.
    assert result.exit_code == 2
    assert result.stderr.count("summary cache hit") == 2
    assert "summary cache miss" not in result.stderr
    assert Report.model_validate_json(result.stdout).suite_status == "inconclusive"
    assert result.stdout == report_path.read_text(encoding="utf-8")
    assert {cache: cache.read_bytes() for cache in caches} == caches


@pytest.mark.parametrize(
    "overrides",
    [
        ("--seed", "17"),
        ("--resamples", "2000"),
        ("--seed", "17", "--resamples", "2000"),
    ],
)
def test_compare_records_bootstrap_overrides_and_defaults(
    tmp_path: Path, overrides: tuple[str, ...]
) -> None:
    # Given: eligible, disjoint multi-run cohorts with a clearly better current value.
    arguments = compare_inputs(tmp_path, multi_run=True)

    # When: seed, resamples, or both are overridden through the real CLI.
    result = CliRunner().invoke(
        app,
        [
            *arguments,
            *overrides,
            "--report-json",
            str(tmp_path / "report.json"),
            "--json",
        ],
    )

    # Then: the report proves bootstrap ran and retains supplied and default options.
    assert result.exit_code == 0
    report = Report.model_validate_json(result.stdout)
    metric = report.metrics[0]
    assert report.suite_status == "pass"
    assert metric.method == "cohort_bootstrap"
    assert (metric.current.count, metric.baseline.count) == (5, 10)
    assert metric.exclusions == ()
    assert metric.options.effective_seed == (17 if "--seed" in overrides else 42)
    expected_resamples = 2000 if "--resamples" in overrides else 10_000
    assert metric.options.requested_resamples == expected_resamples
    assert metric.options.effective_resamples == expected_resamples
    assert metric.options.requested_alpha == 0.05
    assert metric.options.effective_alpha == 0.05


@pytest.mark.parametrize("override", [("--seed", "17"), ("--resamples", "2000")])
def test_compare_rejects_bootstrap_overrides_for_baseline_reference(
    tmp_path: Path, compare_arguments: list[str], override: tuple[str, str]
) -> None:
    # Given: one eligible current run and a sufficient reference baseline.
    # When: bootstrap-only options are supplied to the baseline-reference comparison.
    result = CliRunner().invoke(
        app,
        [
            *compare_arguments,
            *override,
            "--report-json",
            str(tmp_path / "report.json"),
            "--report-md",
            str(tmp_path / "report.md"),
            "--json",
        ],
    )

    # Then: invalid method options cannot emit reports or machine-readable stdout.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert "error: invalid command input" in result.stderr
    assert not list(tmp_path.glob("report.*"))


def test_compare_rejects_duplicate_report_destinations(
    tmp_path: Path, compare_arguments: list[str]
) -> None:
    # Given: both requested formats target the same new path.
    output = tmp_path / "report"

    # When: even forced comparison receives duplicate destinations.
    result = CliRunner().invoke(
        app,
        [
            *compare_arguments,
            "--report-json",
            str(output),
            "--report-md",
            str(output),
            "--force",
        ],
    )

    # Then: duplicate-path preflight rejects the invocation before any report write.
    assert result.exit_code == 3
    assert not output.exists()


@pytest.mark.parametrize("format_name", ["json", "md"])
def test_compare_ignores_existing_omitted_output(
    tmp_path: Path, compare_arguments: list[str], format_name: str
) -> None:
    # Given: a new requested output but an existing unrequested sibling.
    output = tmp_path / f"report.{format_name}"
    sibling = tmp_path / ("report.md" if format_name == "json" else "report.json")
    _ = sibling.write_text("keep-omitted", encoding="utf-8")

    # When: compare requests only the new output without --force.
    result = CliRunner().invoke(
        app, [*compare_arguments, f"--report-{format_name}", str(output)]
    )

    # Then: the unrequested existing path neither blocks nor gets replaced.
    assert result.exit_code == 2
    assert "inconclusive" in output.read_text(encoding="utf-8")
    assert sibling.read_text(encoding="utf-8") == "keep-omitted"
