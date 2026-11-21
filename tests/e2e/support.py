from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import (
    TYPE_CHECKING,
    Final,
    Literal,
    Protocol,
    TypeGuard,
    override,
    runtime_checkable,
)

if TYPE_CHECKING:
    from collections.abc import Generator

_ROOT: Final = Path(__file__).parents[2]
_FIXTURE_SERVER: Final = _ROOT / "tests/fixtures/mock_prometheus_server.py"
_STARTUP_TIMEOUT_SECONDS: Final = 5.0
_CLEANUP_TIMEOUT_SECONDS: Final = 5.0

type PlatformName = Literal["nt", "posix"]


class FixtureServerStartupReason(StrEnum):
    STDOUT_NOT_BYTE_STREAM = "stdout is not a byte stream"
    STDERR_NOT_BYTE_STREAM = "stderr is not a byte stream"
    ENDPOINT_OUTPUT_TIMED_OUT = "endpoint output timed out"
    ENDPOINT_OUTPUT_CLOSED = "endpoint output closed"


@runtime_checkable
class _ByteReader(Protocol):
    def close(self) -> None: ...

    def read(self, size: int = -1, /) -> bytes: ...

    def readline(self, size: int = -1, /) -> bytes: ...


@dataclass(slots=True)
class FixtureServerStartupError(RuntimeError):
    reason: FixtureServerStartupReason
    stderr: str = ""

    @override
    def __str__(self) -> str:
        return (
            "mock Prometheus server failed to start: "
            f"{self.reason}; stderr={self.stderr!r}"
        )


@dataclass(slots=True)
class FixtureServerCleanupError(RuntimeError):
    timeout_seconds: float

    @override
    def __str__(self) -> str:
        return f"mock Prometheus server did not stop within {self.timeout_seconds}s"


def perfcheck_executable(venv: Path, *, platform: PlatformName | None = None) -> Path:
    """Resolve the generated perfcheck console script in a virtual environment."""
    match platform:
        case "nt":
            return venv / "Scripts/perfcheck.exe"
        case "posix":
            return venv / "bin/perfcheck"
        case None:
            executable = "perfcheck.exe" if os.name == "nt" else "perfcheck"
            directory = "Scripts" if os.name == "nt" else "bin"
            return venv / directory / executable


@contextmanager
def mock_prometheus_endpoint(
    fixture: Path,
    *,
    echo_token_body: str | None = None,
    echo_basic_body: str | None = None,
) -> Generator[str]:
    """Start the local Prometheus fixture and yield its endpoint until cleanup."""
    command = [
        sys.executable,
        str(_FIXTURE_SERVER),
        "--port",
        "0",
        "--fixture",
        str(fixture),
    ]
    if echo_token_body is not None:
        command.extend(("--echo-token-body", echo_token_body))
    if echo_basic_body is not None:
        command.extend(("--echo-basic-body", echo_basic_body))
    process = subprocess.Popen[bytes](
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout_candidate = process.stdout
    stderr_candidate = process.stderr
    if not _is_byte_reader(stdout_candidate):
        _stop_process(process)
        raise FixtureServerStartupError(
            FixtureServerStartupReason.STDOUT_NOT_BYTE_STREAM
        )
    if not _is_byte_reader(stderr_candidate):
        _stop_process(process)
        stdout_candidate.close()
        raise FixtureServerStartupError(
            FixtureServerStartupReason.STDERR_NOT_BYTE_STREAM
        )
    stdout = stdout_candidate
    stderr = stderr_candidate
    lines, reader = _start_stdout_reader(stdout)
    try:
        try:
            endpoint = _await_endpoint(lines)
        except FixtureServerStartupError as error:
            _stop_process(process)
            stderr_text = stderr.read().decode()
            raise FixtureServerStartupError(error.reason, stderr_text) from error
        yield endpoint
    finally:
        try:
            _stop_process(process)
        finally:
            reader.join(timeout=_CLEANUP_TIMEOUT_SECONDS)
            stdout.close()
            stderr.close()


def _start_stdout_reader(stdout: _ByteReader) -> tuple[Queue[bytes], Thread]:
    lines: Queue[bytes] = Queue(maxsize=1)
    reader = Thread(target=_put_stdout_line, args=(stdout, lines))
    reader.start()
    return lines, reader


def _await_endpoint(lines: Queue[bytes]) -> str:
    try:
        endpoint = lines.get(timeout=_STARTUP_TIMEOUT_SECONDS).decode().strip()
    except Empty as error:
        raise FixtureServerStartupError(
            FixtureServerStartupReason.ENDPOINT_OUTPUT_TIMED_OUT
        ) from error
    if endpoint:
        return endpoint
    raise FixtureServerStartupError(FixtureServerStartupReason.ENDPOINT_OUTPUT_CLOSED)


def _put_stdout_line(stdout: _ByteReader, lines: Queue[bytes]) -> None:
    lines.put(stdout.readline())


def _is_byte_reader(stream: _ByteReader | None) -> TypeGuard[_ByteReader]:
    return isinstance(stream, _ByteReader)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        _ = process.wait(timeout=_CLEANUP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        try:
            _ = process.wait(timeout=_CLEANUP_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as error:
            raise FixtureServerCleanupError(_CLEANUP_TIMEOUT_SECONDS) from error
