from __future__ import annotations

import http.client
import os
import sys
from pathlib import Path
from typing import ClassVar, Literal
from urllib.parse import urlencode, urlparse

import pytest
from examples._support import (
    FixtureServerStartupError,
    LocalCommandTimeoutError,
    example_workspace,
    mock_prometheus_endpoint,
    perfcheck_executable,
    run_local_command,
    sanitized_environment,
)
from pydantic import BaseModel, ConfigDict, Field

from tests import examples_check
from tests.examples_check import EXAMPLE_NOTEBOOKS, run_standalone_notebook

_ROOT = Path(__file__).parents[1]
_FIXTURE = _ROOT / "examples/fixtures/prometheus-matrix.json"
_PASS_POLICY = _ROOT / "tests/fixtures/policy-pass.json"
_LESSON_PATHS = EXAMPLE_NOTEBOOKS
_LESSON_OUTPUT_EVIDENCE = (
    (_LESSON_PATHS[0], "collect"),
    (_LESSON_PATHS[1], "metric_record_count"),
    (_LESSON_PATHS[2], "eligibility"),
    (_LESSON_PATHS[3], '"suite_status": "pass"'),
    (_LESSON_PATHS[4], "Handled failure: exit status 3 — error: invalid command input"),
)
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


class _MatrixSeries(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    values: tuple[tuple[float, str], ...]


class _MatrixData(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    result_type: Literal["matrix"] = Field(alias="resultType")
    result: tuple[_MatrixSeries, ...]


class _MatrixResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["success"]
    data: _MatrixData


class _ErrorResponse(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    status: Literal["error"]


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
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
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


def test_fixture_server_returns_deterministic_matrix_for_known_query() -> None:
    # Given: the self-contained fixture server and one known query.
    with mock_prometheus_endpoint(_FIXTURE) as endpoint:
        parsed = urlparse(endpoint)
        assert parsed.hostname is not None
        assert parsed.port is not None
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=1)

        # When: the fixed range-query request reaches the loopback fixture.
        connection.request(
            "POST",
            "/api/v1/query_range",
            body=urlencode(
                {"query": "pass_metric", "start": "2026-07-01T10:00:00+00:00"}
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        payload = _MatrixResponse.model_validate_json(response.read())
        connection.close()

        # Then: the fixture emits the sanitized deterministic Prometheus matrix.
        assert response.status == 200
        assert payload.status == "success"
        assert payload.data.result_type == "matrix"
        assert payload.data.result[0].values == tuple(
            (1782900000.0 + (15 * index), "10.0") for index in range(41)
        )


def test_fixture_server_rejects_unknown_query() -> None:
    # Given: the self-contained fixture server and an unknown query.
    with mock_prometheus_endpoint(_FIXTURE) as endpoint:
        parsed = urlparse(endpoint)
        assert parsed.hostname is not None
        assert parsed.port is not None
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=1)

        # When: the unknown range query is sent.
        connection.request(
            "POST",
            "/api/v1/query_range",
            body=urlencode(
                {"query": "unknown_metric", "start": "2026-07-01T10:00:00+00:00"}
            ),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        response = connection.getresponse()
        payload = _ErrorResponse.model_validate_json(response.read())
        connection.close()

        # Then: it fails deterministically without echoing request data.
        assert (response.status, payload.status) == (400, "error")


def test_fixture_server_reports_readiness_failure_without_credential_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a missing fixture and a fake parent bearer token.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")

    # When: fixture startup cannot announce readiness before its timeout.
    with (
        pytest.raises(FixtureServerStartupError) as error,
        mock_prometheus_endpoint(tmp_path / "missing.json", readiness_timeout=0.5),
    ):
        pass

    # Then: the stable startup error discloses neither token nor child diagnostics.
    assert "fake-bearer-token" not in str(error.value)


@pytest.mark.parametrize("lesson_path", _LESSON_PATHS)
def test_curriculum_scope_has_standalone_marimo_scripts_in_teaching_order(
    lesson_path: Path,
) -> None:
    # Given: one lesson from the first curriculum segment.

    # When: its source is inspected as a notebook script.
    source = lesson_path.read_text(encoding="utf-8")

    # Then: it has the stable section order and the executable Marimo boundary.
    sections = ("## Goal", "## Inputs", "## Run", "## Evidence", "## Takeaway")
    positions = tuple(source.index(section) for section in sections)
    assert positions == tuple(sorted(positions))
    assert "app = marimo.App(" in source
    assert "@app.cell" in source
    assert 'if __name__ == "__main__":' in source
    assert "app.run()" in source
    assert "# /// script" not in source


@pytest.mark.parametrize(("lesson_path", "expected_evidence"), _LESSON_OUTPUT_EVIDENCE)
def test_no_generated_example_output_persists_after_lesson_execution(
    lesson_path: Path,
    expected_evidence: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an isolated current directory and a fake parent credential.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    example_paths_before = tuple(
        sorted(path.relative_to(_ROOT) for path in (_ROOT / "examples").rglob("*"))
    )
    # When: the public checker runs the absolute notebook in a fresh workspace.
    result = run_standalone_notebook(lesson_path)

    # Then: it succeeds and only renders the stable teaching headings.
    assert result.returncode == 0, result.stderr
    assert "Goal" in result.stdout
    assert "Takeaway" in result.stdout
    assert expected_evidence in result.stdout
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr
    assert (
        tuple(
            sorted(path.relative_to(_ROOT) for path in (_ROOT / "examples").rglob("*"))
        )
        == example_paths_before
    )


def test_curriculum_index_lists_each_lesson_once_in_numeric_order() -> None:
    # Given: the public curriculum index and the canonical lesson tuple.
    index = (_ROOT / "examples/README.md").read_text(encoding="utf-8")

    # When: each canonical lesson link is inspected.
    lesson_links = tuple(
        f"[{notebook.name}]({notebook.name})" for notebook in EXAMPLE_NOTEBOOKS
    )

    # Then: every lesson is linked once, in the teaching order.
    assert all(index.count(link) == 1 for link in lesson_links)
    assert tuple(index.index(link) for link in lesson_links) == tuple(
        sorted(index.index(link) for link in lesson_links)
    )


def test_documentation_scope_preserves_cli_only_setup_and_explicit_commands() -> None:
    # Given: the public curriculum index.
    index = (_ROOT / "examples/README.md").read_text(encoding="utf-8")

    # When: the documented setup and per-lesson commands are inspected.
    required_commands = tuple(
        command
        for notebook in EXAMPLE_NOTEBOOKS
        for command in (
            f"uv run --group examples marimo edit examples/{notebook.name}",
            f"uv run --group examples marimo run examples/{notebook.name}",
            f"uv --directory . run --group examples python examples/{notebook.name}",
        )
    )

    # Then: a contributor can set up, author, consume, or script every lesson.
    assert "uv sync --group examples" in index
    assert all(command in index for command in required_commands)


def test_validate_repository_course_reports_a_missing_index_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: a complete temporary course whose index omits the final lesson.
    lessons = tuple(tmp_path / notebook.name for notebook in EXAMPLE_NOTEBOOKS)
    for lesson in lessons:
        _ = lesson.write_text("import marimo\n", encoding="utf-8")
    linked_lessons = lessons[:-1]
    _ = (tmp_path / "README.md").write_text(
        "\n".join(f"[{lesson.name}]({lesson.name})" for lesson in linked_lessons),
        encoding="utf-8",
    )
    monkeypatch.setattr(examples_check, "_EXAMPLES_DIRECTORY", tmp_path)
    monkeypatch.setattr(examples_check, "EXAMPLE_NOTEBOOKS", lessons)

    # When: the shared validator inspects the incomplete public index.
    with pytest.raises(
        AssertionError, match=r"curriculum index must link 05-failures-and-ci\.py"
    ):
        examples_check.validate_repository_course()

    # Then: the missing entry is identified rather than silently accepted.


@pytest.mark.parametrize("lesson_path", EXAMPLE_NOTEBOOKS)
def test_no_metadata_or_blanket_lesson_suppressions(lesson_path: Path) -> None:
    # Given: one canonical Marimo lesson.

    # When: its source is read.
    source = lesson_path.read_text(encoding="utf-8")

    # Then: dependency metadata remains in the optional project group and
    # framework cells cannot bypass the repository's strict analysis settings.
    assert "# /// script" not in source
    assert "# pyright: basic" not in source
    assert "# ruff: noqa:" not in source


def test_tampered_raw_artifact_is_rejected_before_summary_is_written(
    tmp_path: Path,
) -> None:
    # Given: a raw run created through the public collect command and then altered.
    raw_path = tmp_path / "raw.json"
    summary_path = tmp_path / "summary.json"
    with mock_prometheus_endpoint(_FIXTURE) as endpoint:
        collect = run_local_command(
            (
                str(perfcheck_executable()),
                "collect",
                "--suite",
                str(_PASS_POLICY),
                "--prometheus-url",
                endpoint,
                "--run-id",
                "lesson-tampered",
                "--start",
                "2026-07-01T10:00:00Z",
                "--end",
                "2026-07-01T10:10:00Z",
                "--out",
                str(raw_path),
            ),
            cwd=tmp_path,
        )
    _ = raw_path.write_bytes(
        raw_path.read_bytes().replace(
            b'"run_id":"lesson-tampered"', b'"run_id":"tampered-run"', 1
        )
    )

    # When: summarize receives the tampered raw artifact through the public CLI.
    summarize = run_local_command(
        (
            str(perfcheck_executable()),
            "summarize",
            "--policy",
            str(_PASS_POLICY),
            "--run",
            str(raw_path),
            "--out",
            str(summary_path),
        ),
        cwd=tmp_path,
    )

    # Then: the generic input error is returned and no summary is persisted.
    assert collect.returncode == 0
    assert summarize.returncode == 3
    assert "error: invalid command input" in summarize.stderr
    assert not summary_path.exists()


def test_comparison_lesson_reports_known_pass_with_both_temporary_formats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the standalone comparison lesson and an unsafe parent credential.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    lesson_path = _ROOT / "examples/04-compare.py"

    # When: the lesson collects, summarizes, and compares its local fixture cohorts.
    result = run_standalone_notebook(lesson_path)

    # Then: both temporary report formats describe the known passing decision safely.
    assert result.returncode == 0, result.stderr
    assert '"suite_status": "pass"' in result.stdout
    assert "JSON report (temporary)" in result.stdout
    assert "Markdown report (temporary)" in result.stdout
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr


def test_failures_lesson_handles_existing_report_preflight_without_secret_leakage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: the standalone failure lesson and a parent-only credential.
    monkeypatch.setenv("PERFCHECK_PROMETHEUS_BEARER_TOKEN", "fake-bearer-token")
    lesson_path = _ROOT / "examples/05-failures-and-ci.py"

    # When: the lesson catches its documented report-output preflight failure.
    result = run_standalone_notebook(lesson_path)

    # Then: it preserves the exact CLI outcome while the notebook itself succeeds.
    assert result.returncode == 0, result.stderr
    assert (
        "Handled failure: exit status 3 — error: invalid command input" in result.stdout
    )
    assert "fake-bearer-token" not in result.stdout
    assert "fake-bearer-token" not in result.stderr
