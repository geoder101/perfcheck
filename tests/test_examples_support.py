from __future__ import annotations

import os
import sys
from pathlib import Path

import marimo as mo
import pytest
from examples import _markdown
from examples._support import (
    COMPARE_COHORT,
    FAILURE_COHORT,
    CollectRequest,
    CompareRequest,
    LocalCommandTimeoutError,
    SummaryRequest,
    collect_arguments,
    compare_arguments,
    example_workspace,
    lesson_context,
    parse_raw_evidence,
    parse_report_evidence,
    parse_summary_evidence,
    perfcheck_executable,
    run_local_command,
    sanitized_environment,
    summarize_arguments,
)
from pydantic import ValidationError

_ROOT = Path(__file__).parents[1]
_FIXTURE = _ROOT / "examples/fixtures/prometheus-matrix.json"
_PASS_POLICY = _ROOT / "tests/fixtures/policy-pass.json"
_ALLOWED_ENVIRONMENT_NAMES = (
    "PATH",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "HOME",
    "USERPROFILE",
    "TMP",
    "TEMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
)


def test_markdown_helper_replaces_output_with_rendered_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a markdown renderer and output replacement boundary.
    rendered = mo.Html("<p>lesson text</p>")
    rendered_texts: list[str] = []
    replaced_outputs: list[mo.Html] = []

    def render_markdown(text: str) -> mo.Html:
        rendered_texts.append(text)
        return rendered

    def replace_output(value: mo.Html) -> None:
        replaced_outputs.append(value)

    monkeypatch.setattr(mo, "md", render_markdown)
    monkeypatch.setattr(mo.output, "replace", replace_output)

    # When: a lesson emits markdown through the isolated helper.
    _markdown.md("lesson text")

    # Then: the rendered Html is delegated to Marimo's output replacement.
    assert rendered_texts == ["lesson text"]
    assert replaced_outputs == [rendered]


def test_secrets_are_excluded_from_the_sanitized_child_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: allowed platform values and fake credential values in the parent process.
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "fake-cloud-token")

    # When: the example child environment is prepared.
    environment = sanitized_environment()

    # Then: only present allowlisted values remain and credentials are excluded.
    assert environment["LANG"] == "C.UTF-8"
    assert "PERFCHECK_PROMETHEUS_BEARER_TOKEN" not in environment
    assert "AWS_SESSION_TOKEN" not in environment
    assert set(environment) <= {
        "PATH",
        "SystemRoot",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "HOME",
        "USERPROFILE",
        "TMP",
        "TEMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    }


def test_sanitized_environment_starts_empty_when_parent_has_no_allowlisted_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a parent environment containing only an arbitrary unsafe value.
    for name in _ALLOWED_ENVIRONMENT_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("UNSAFE_PARENT_VALUE", "not-forwarded")

    # When: the child environment is constructed.
    environment = sanitized_environment()

    # Then: construction has an observable empty origin rather than inherited state.
    assert environment == {}


def test_run_local_command_excludes_bearer_token_from_parent_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: fake bearer and cloud credentials in the parent environment.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "fake-cloud-token")

    # When: a helper-managed child reports its credential presence.
    result = run_local_command(
        (
            sys.executable,
            "-c",
            (
                "import os; print('PERFCHECK_PROMETHEUS_BEARER_TOKEN' in os.environ); "
                "print('AWS_SESSION_TOKEN' in os.environ)"
            ),
        ),
        cwd=tmp_path,
    )

    # Then: neither credential reaches the child process.
    assert result.stdout.splitlines() == ["False", "False"]


def test_run_local_command_preserves_failure_despite_success_text(
    tmp_path: Path,
) -> None:
    # Given: a child that prints a misleading success message before failing.

    # When: the helper runs its explicit argument list.
    result = run_local_command(
        (sys.executable, "-c", "print('success'); raise SystemExit(7)"),
        cwd=tmp_path,
    )

    # Then: its nonzero exit status remains observable.
    assert (result.returncode, result.stdout.strip()) == (7, "success")


def test_run_local_command_terminates_hung_child_after_timeout(tmp_path: Path) -> None:
    # Given: a child that records its PID then sleeps beyond the bounded timeout.
    child_pid_path = tmp_path / "child.pid"
    child_program = (
        "import os, pathlib, time; "
        f"pathlib.Path({str(child_pid_path)!r}).write_text("
        "str(os.getpid())); time.sleep(60)"
    )

    # When: the helper runs the hung child with a short explicit bound.
    with pytest.raises(LocalCommandTimeoutError) as error:
        _ = run_local_command(
            (
                sys.executable,
                "-c",
                child_program,
            ),
            cwd=tmp_path,
            timeout_seconds=0.1,
        )

    # Then: the safe typed error reports the bound and the direct child is gone.
    child_pid = int(child_pid_path.read_text(encoding="utf-8"))
    child_pid_path.unlink()
    assert error.value.timeout_seconds == 0.1
    with pytest.raises(OSError, match=r"(?:WinError 87|Errno 3)") as stopped:
        os.kill(child_pid, 0)
    if os.name == "nt":
        assert stopped.value.winerror == 87  # ERROR_INVALID_PARAMETER: PID is gone.
    else:
        assert isinstance(stopped.value, ProcessLookupError)
    assert not child_pid_path.exists()


def test_example_workspace_is_unique_and_removed_after_context() -> None:
    # Given: the example workspace context manager.

    # When: two isolated workspaces are allocated and their contexts exit.
    with example_workspace() as first, example_workspace() as second:
        _ = (first / "state.txt").write_text("first", encoding="utf-8")
        assert first != second
        assert not (second / "state.txt").exists()

    # Then: both temporary workspaces have been cleaned up.
    assert not first.exists()
    assert not second.exists()


def test_perfcheck_executable_uses_project_local_console_script() -> None:
    # Given: the managed Python executable.

    # When: the example helper resolves the console command.
    executable = perfcheck_executable()

    # Then: it is adjacent to Python using the platform-specific script name.
    expected_name = "perfcheck.exe" if os.name == "nt" else "perfcheck"
    assert executable == Path(sys.executable).parent / expected_name


def test_lesson_context_resolves_repository_fixtures() -> None:
    # Given: the shared lesson context factory.

    # When: a lesson requests its local CLI resources.
    context = lesson_context()

    # Then: its paths stay rooted in this checkout's bundled fixtures.
    assert context.repository_root == _ROOT
    assert context.policy_path == _PASS_POLICY
    assert context.fixture_path == _FIXTURE
    assert context.executable == perfcheck_executable()


def test_collect_arguments_build_the_collect_cli_contract() -> None:
    # Given: a lesson context and deterministic collection request.
    context = lesson_context()
    request = CollectRequest(
        endpoint="http://127.0.0.1:12345",
        run=COMPARE_COHORT[0],
        output_path=Path("raw.json"),
    )

    # When: the collect command arguments are built.
    arguments = collect_arguments(context, request)

    # Then: the public CLI receives the fixed UTC interval and output path.
    assert arguments[-8:] == (
        "--run-id",
        "lesson-baseline-1",
        "--start",
        "2026-07-01T10:00:00Z",
        "--end",
        "2026-07-01T10:10:00Z",
        "--out",
        "raw.json",
    )


def test_summarize_arguments_build_the_summary_cli_contract() -> None:
    # Given: a lesson context and temporary raw and summary paths.
    context = lesson_context()
    request = SummaryRequest(Path("raw.json"), Path("summary.json"))

    # When: the summarize command arguments are built.
    arguments = summarize_arguments(context, request)

    # Then: the policy, source raw run, and output are explicit.
    assert arguments[-6:] == (
        "--policy",
        str(_PASS_POLICY),
        "--run",
        "raw.json",
        "--out",
        "summary.json",
    )


def test_compare_arguments_build_the_fixed_cohort_cli_contract() -> None:
    # Given: a lesson context with the fixed comparison cohort's paths.
    context = lesson_context()
    paths = tuple(Path(f"{run.run_id}.json") for run in COMPARE_COHORT)

    # When: the compare command arguments are built for summaries.
    request = CompareRequest(
        current_paths=paths[2:],
        baseline_paths=paths[:2],
        report_json_path=Path("comparison.json"),
        report_markdown_path=Path("comparison.md"),
        seed=20260704,
        resamples=1000,
    )
    arguments = compare_arguments(context, request)

    # Then: the cohort ordering and deterministic comparison settings are retained.
    assert arguments[-6:] == (
        "--report-md",
        "comparison.md",
        "--seed",
        "20260704",
        "--resamples",
        "1000",
    )
    assert FAILURE_COHORT[0].run_id == "failure-baseline-1"


def test_evidence_parsers_return_only_displayed_fields() -> None:
    # Given: minimal artifact payloads with the fields each lesson displays.

    # When: raw, summary, and report evidence cross the JSON boundary.
    raw = parse_raw_evidence(
        b'{"run_id":"raw-1","schema_version":1,"metric_records":[{}]}'
    )
    summary = parse_summary_evidence(
        b"".join(
            (
                b'{"summary_id":"summary-1","source_run_id":"raw-1",',
                b'"metric_records":[{"summary":{"eligibility":{"eligible":true}}}]}',
            )
        )
    )
    report = parse_report_evidence(
        b"".join(
            (
                b'{"suite_status":"pass","metrics":[',
                b'{"metric_id":"latency","method":"bootstrap","status":"pass"}]}',
            )
        )
    )

    # Then: callers receive no unvalidated artifact payload.
    assert raw == {"run_id": "raw-1", "schema_version": 1, "metric_record_count": 1}
    assert summary == {
        "summary_id": "summary-1",
        "source_run_id": "raw-1",
        "metric_record_count": 1,
        "eligible": True,
    }
    assert report == {
        "suite_status": "pass",
        "metric_id": "latency",
        "method": "bootstrap",
        "metric_status": "pass",
    }


def test_summary_evidence_parser_rejects_empty_displayed_records() -> None:
    # Given: a summary payload without a metric record to display.
    payload = b'{"summary_id":"summary-1","source_run_id":"raw-1","metric_records":[]}'

    # When: the payload crosses the lesson JSON boundary.
    with pytest.raises(ValidationError):
        _ = parse_summary_evidence(payload)

    # Then: no later lesson cell can index an unvalidated empty collection.
