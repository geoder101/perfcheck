from __future__ import annotations

from pathlib import Path  # noqa: TC003 - pytest resolves the fixture annotation.

import pytest
from typer.testing import CliRunner

from perfcheck.cli import app
from perfcheck.storage import (
    load_artifact,
    summary_cache_path,
    write_artifact,
)
from perfcheck.summary_models import SummaryArtifact
from tests.cli_support import cli_policy, cli_run, write_cli_policy


def test_summarize_writes_canonical_summary_without_stdout(
    tmp_path: Path,
) -> None:
    # Given: verified raw evidence and its matching canonical policy.
    policy = cli_policy()
    policy_path = tmp_path / "policy.json"
    raw_path = tmp_path / "run.json"
    summary_path = tmp_path / "summary.json"
    write_cli_policy(policy_path, policy)
    write_artifact(raw_path, cli_run(policy, 1, 10.0))

    # When: summarize receives its explicit output path.
    result = CliRunner().invoke(
        app,
        [
            "summarize",
            "--policy",
            str(policy_path),
            "--run",
            str(raw_path),
            "--out",
            str(summary_path),
        ],
    )

    # Then: it writes a verified summary and reserves stdout for machine output.
    assert result.exit_code == 0
    assert result.stdout == ""
    payload = SummaryArtifact.model_validate_json(summary_path.read_bytes())
    assert payload.artifact_type == "summary"


@pytest.mark.parametrize("force", [False, True])
def test_summarize_requires_force_to_replace_existing_destination(
    tmp_path: Path, force: bool
) -> None:
    # Given: valid evidence and an existing destination containing user bytes.
    policy = cli_policy()
    raw = cli_run(policy, 1, 10.0)
    policy_path, raw_path, output = (
        tmp_path / name for name in ("policy.json", "run.json", "summary.json")
    )
    write_cli_policy(policy_path, policy)
    write_artifact(raw_path, raw)
    original = b"keep-summary\x00\xff"
    _ = output.write_bytes(original)
    arguments = [
        "summarize",
        "--policy",
        str(policy_path),
        "--run",
        str(raw_path),
        "--out",
        str(output),
    ]
    if force:
        arguments.append("--force")

    # When: summarize is invoked with or without explicit replacement permission.
    result = CliRunner().invoke(app, arguments)

    # Then: replacement is verified against its source, or the bytes are preserved.
    assert result.exit_code == (0 if force else 3)
    assert result.stdout == ""
    if force:
        summary = load_artifact(output, source_run=raw)
        assert isinstance(summary, SummaryArtifact)
        assert summary.source_content_sha256 == raw.content_sha256
    else:
        assert output.read_bytes() == original


def test_summarize_preflights_destination_before_loading_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an occupied output and loaders that must not run during preflight.
    output = tmp_path / "summary.json"
    _ = output.write_bytes(b"keep-summary")

    def unexpected_load(_: Path) -> None:
        pytest.fail("input loaded before destination preflight")

    monkeypatch.setattr("perfcheck.cli.load_policy", unexpected_load)
    monkeypatch.setattr("perfcheck.cli.load_raw", unexpected_load)

    # When: missing inputs accompany an existing destination without --force.
    result = CliRunner().invoke(
        app,
        [
            "summarize",
            "--policy",
            str(tmp_path / "missing-policy.json"),
            "--run",
            str(tmp_path / "missing.json"),
            "--out",
            str(output),
        ],
    )

    # Then: output refusal precedes both input loaders and preserves the file.
    assert result.exit_code == 3
    assert result.stdout == ""
    assert (
        result.stderr
        == "error: output path already exists; use --force to replace it\n"
    )
    assert output.read_bytes() == b"keep-summary"


def test_compare_json_writes_exactly_one_report_to_stdout(tmp_path: Path) -> None:
    # Given: two independently summarized raw runs under one policy.
    policy = cli_policy()
    policy_path = tmp_path / "policy.json"
    current_raw = tmp_path / "current.json"
    baseline_raw = tmp_path / "baseline.json"
    current_summary = tmp_path / "current.summary.json"
    baseline_summary = tmp_path / "baseline.summary.json"
    report_json = tmp_path / "report.json"
    report_markdown = tmp_path / "report.md"
    write_cli_policy(policy_path, policy)
    write_artifact(current_raw, cli_run(policy, 1, 11.0))
    write_artifact(baseline_raw, cli_run(policy, 2, 10.0))
    runner = CliRunner()
    for raw_path, summary_path in (
        (current_raw, current_summary),
        (baseline_raw, baseline_summary),
    ):
        assert (
            runner.invoke(
                app,
                [
                    "summarize",
                    "--policy",
                    str(policy_path),
                    "--run",
                    str(raw_path),
                    "--out",
                    str(summary_path),
                ],
            ).exit_code
            == 0
        )

    # When: compare is asked for machine-readable stdout.
    result = runner.invoke(
        app,
        [
            "compare",
            "--policy",
            str(policy_path),
            "--current",
            str(current_summary),
            "--baseline",
            str(baseline_summary),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_markdown),
            "--json",
        ],
    )

    # Then: stdout is one report document and the advisory outcome is inconclusive.
    assert result.exit_code == 2
    assert '"suite_status":"inconclusive"' in result.stdout
    assert report_json.read_text(encoding="utf-8") == result.stdout
    assert report_markdown.exists()


def test_compare_preflight_rejects_existing_reports_without_mutation(
    tmp_path: Path,
) -> None:
    # Given: explicit report destinations that already contain user data.
    report_json = tmp_path / "report.json"
    report_markdown = tmp_path / "report.md"
    _ = report_json.write_text("keep-json", encoding="utf-8")
    _ = report_markdown.write_text("keep-markdown", encoding="utf-8")

    # When: compare is invoked without --force.
    result = CliRunner().invoke(
        app,
        [
            "compare",
            "--policy",
            str(tmp_path / "missing-policy.json"),
            "--current",
            str(tmp_path / "current.json"),
            "--baseline",
            str(tmp_path / "baseline.json"),
            "--report-json",
            str(report_json),
            "--report-md",
            str(report_markdown),
        ],
    )

    # Then: preflight wins over later input errors and leaves both files unchanged.
    assert result.exit_code == 3
    assert report_json.read_text(encoding="utf-8") == "keep-json"
    assert report_markdown.read_text(encoding="utf-8") == "keep-markdown"


def test_compare_derives_raw_summaries_without_cache_then_writes_opted_in_cache(
    tmp_path: Path,
) -> None:
    # Given: raw convenience inputs with no sibling summary caches.
    policy = cli_policy()
    policy_path = tmp_path / "policy.json"
    current_raw = tmp_path / "current.json"
    baseline_raw = tmp_path / "baseline.json"
    report_json = tmp_path / "report.json"
    report_markdown = tmp_path / "report.md"
    write_cli_policy(policy_path, policy)
    write_artifact(current_raw, cli_run(policy, 1, 11.0))
    write_artifact(baseline_raw, cli_run(policy, 2, 10.0))
    runner = CliRunner()
    arguments = [
        "compare",
        "--policy",
        str(policy_path),
        "--current",
        str(current_raw),
        "--baseline",
        str(baseline_raw),
        "--report-json",
        str(report_json),
        "--report-md",
        str(report_markdown),
    ]

    # When: compare derives summaries without the explicit cache-write option.
    first = runner.invoke(app, arguments)

    # Then: it succeeds inconclusively and does not mutate either input sibling.
    assert first.exit_code == 2
    assert not summary_cache_path(current_raw, policy.policy_sha256).exists()
    assert not summary_cache_path(baseline_raw, policy.policy_sha256).exists()

    # When: the same raw inputs opt into cache materialization and report replacement.
    second = runner.invoke(app, [*arguments, "--write-summary-cache", "--force"])

    # Then: both canonical sibling caches are atomically materialized.
    assert second.exit_code == 2
    assert summary_cache_path(current_raw, policy.policy_sha256).exists()
    assert summary_cache_path(baseline_raw, policy.policy_sha256).exists()
