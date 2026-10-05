from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Iterator


_ROOT = Path(__file__).parents[2]
_SERVER = _ROOT / "tests/fixtures/mock_prometheus_server.py"
_PROMETHEUS_FIXTURE = _ROOT / "tests/fixtures/prometheus/matrix.json"


@pytest.fixture
def mock_prometheus_endpoint() -> Iterator[str]:
    endpoint_read, endpoint_write = os.pipe()
    process: subprocess.Popen[bytes] = subprocess.Popen(  # noqa: S603 - fixed local fixture command.
        [
            sys.executable,
            str(_SERVER),
            "--port",
            "0",
            "--fixture",
            str(_PROMETHEUS_FIXTURE),
        ],
        stdout=endpoint_write,
        stderr=subprocess.PIPE,
    )
    os.close(endpoint_write)
    try:
        yield os.read(endpoint_read, 4096).decode().strip()
    finally:
        process.terminate()
        assert process.stderr is not None
        try:
            _ = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            _ = process.wait(timeout=5)
        finally:
            os.close(endpoint_read)
            process.stderr.close()


@pytest.mark.parametrize(
    ("script_name", "expected_exit"),
    [
        ("wheel-pass.sh", 0),
        ("wheel-fail.sh", 1),
        ("wheel-inconclusive.sh", 2),
    ],
)
def test_installed_command_workflow_writes_both_report_formats_for_each_verdict(
    mock_prometheus_endpoint: str,
    script_name: str,
    expected_exit: int,
    tmp_path: Path,
) -> None:
    # Given: an isolated Prometheus fixture and editable command entrypoint.
    binary = Path(sys.executable).parent / "perfcheck"
    verdict = script_name.removeprefix("wheel-").removesuffix(".sh")
    environment = {
        **os.environ,
        "PERFCHECK_BIN": str(binary),
        "PERFCHECK_PROMETHEUS_URL": mock_prometheus_endpoint,
        "PERFCHECK_SMOKE_DIR": str(tmp_path),
    }

    # When: a shell-level installed-command workflow collects, summarizes, and compares.
    result = subprocess.run(  # noqa: S603 - selected static test script.
        [_ROOT / "tests/e2e" / script_name],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )

    # Then: the contractual verdict and both portable report formats are produced.
    assert result.returncode == expected_exit
    report_path = tmp_path / f"{verdict}.json"
    assert report_path.is_file()
    assert (tmp_path / f"{verdict}.md").is_file()
    golden_path = _ROOT / f"tests/fixtures/golden/{verdict}.json"
    assert (
        json.loads(report_path.read_text(encoding="utf-8"))["suite_status"]
        == (json.loads(golden_path.read_text(encoding="utf-8"))["suite_status"])
    )
