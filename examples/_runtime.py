"""Isolated process and workspace helpers for executable examples."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from queue import Empty, Queue
from tempfile import TemporaryDirectory
from threading import Thread
from typing import (
    TYPE_CHECKING,
    Final,
    Protocol,
    TypeGuard,
    override,
    runtime_checkable,
)

if TYPE_CHECKING:
    from collections.abc import Generator, Mapping, Sequence

_ALLOWED_ENVIRONMENT_NAMES: Final = (
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
_SERVER_SCRIPT: Final = Path(__file__).with_name("fixtures") / "mock_prometheus.py"
_STARTUP_TIMEOUT_SECONDS: Final = 5.0
_CLEANUP_TIMEOUT_SECONDS: Final = 5.0
_COMMAND_TIMEOUT_SECONDS: Final = 5.0


class FixtureServerStartupReason(StrEnum):
    """Stable reasons a fixture server cannot become ready."""

    ENDPOINT_OUTPUT_TIMED_OUT = "endpoint output timed out"
    ENDPOINT_OUTPUT_CLOSED = "endpoint output closed"


@runtime_checkable
class _ByteReader(Protocol):
    def close(self) -> None: ...

    def readline(self, size: int = -1, /) -> bytes: ...


@dataclass(slots=True)
class FixtureServerStartupError(RuntimeError):
    """A fixture server did not announce its loopback endpoint."""

    reason: FixtureServerStartupReason

    @override
    def __str__(self) -> str:
        """Render a credential-safe startup error."""
        return f"mock Prometheus server failed to start: {self.reason}"


@dataclass(slots=True)
class FixtureServerCleanupError(RuntimeError):
    """A fixture server resisted bounded process cleanup."""

    timeout_seconds: float

    @override
    def __str__(self) -> str:
        """Render the cleanup timeout without process output."""
        return f"mock Prometheus server did not stop within {self.timeout_seconds}s"


@dataclass(slots=True)
class LocalCommandTimeoutError(RuntimeError):
    """A helper-managed local command exceeded its bounded runtime."""

    timeout_seconds: float

    @override
    def __str__(self) -> str:
        """Render a command-safe timeout without arguments or child output."""
        return f"local command timed out after {self.timeout_seconds}s"


def sanitized_environment() -> Mapping[str, str]:
    """Return the credential-safe allowlisted child environment."""
    environment: dict[str, str] = {}
    for name in _ALLOWED_ENVIRONMENT_NAMES:
        value = os.environ.get(name)
        if value is not None:
            environment[name] = value
    return environment


@contextmanager
def example_workspace() -> Generator[Path]:
    """Yield a fresh example workspace that is removed after use."""
    with TemporaryDirectory(prefix="perfcheck-example-") as directory:
        yield Path(directory)


def perfcheck_executable() -> Path:
    """Resolve the project-local console executable beside managed Python."""
    executable_name = "perfcheck.exe" if os.name == "nt" else "perfcheck"
    return Path(sys.executable).parent / executable_name


def run_local_command(
    arguments: Sequence[str],
    *,
    cwd: Path,
    timeout_seconds: float = _COMMAND_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """Run an argument-list child with safe environment and bounded cleanup."""
    try:
        return subprocess.run(  # noqa: S603 - caller supplies an explicit local executable.
            arguments,
            check=False,
            cwd=cwd,
            capture_output=True,
            env=sanitized_environment(),
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        raise LocalCommandTimeoutError(timeout_seconds) from error


@contextmanager
def mock_prometheus_endpoint(
    fixture: Path, *, readiness_timeout: float = _STARTUP_TIMEOUT_SECONDS
) -> Generator[str]:
    """Run the example fixture on loopback port zero and clean it up."""
    process = subprocess.Popen[bytes](
        [sys.executable, str(_SERVER_SCRIPT), "--port", "0", "--fixture", str(fixture)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=sanitized_environment(),
    )
    stdout_candidate = process.stdout
    if not _is_byte_reader(stdout_candidate):
        _stop_process(process)
        raise FixtureServerStartupError(
            FixtureServerStartupReason.ENDPOINT_OUTPUT_CLOSED
        )
    stdout = stdout_candidate
    lines, reader = _start_stdout_reader(stdout)
    try:
        yield _await_endpoint(lines, readiness_timeout)
    except FixtureServerStartupError:
        _stop_process(process)
        raise
    finally:
        try:
            _stop_process(process)
        finally:
            reader.join(timeout=_CLEANUP_TIMEOUT_SECONDS)
            stdout.close()


def _start_stdout_reader(stdout: _ByteReader) -> tuple[Queue[bytes], Thread]:
    lines: Queue[bytes] = Queue(maxsize=1)
    reader = Thread(target=_put_stdout_line, args=(stdout, lines), daemon=True)
    reader.start()
    return lines, reader


def _put_stdout_line(stdout: _ByteReader, lines: Queue[bytes]) -> None:
    lines.put(stdout.readline())


def _is_byte_reader(stream: _ByteReader | None) -> TypeGuard[_ByteReader]:
    return isinstance(stream, _ByteReader)


def _await_endpoint(lines: Queue[bytes], timeout_seconds: float) -> str:
    try:
        endpoint = lines.get(timeout=timeout_seconds).decode().strip()
    except Empty as error:
        raise FixtureServerStartupError(
            FixtureServerStartupReason.ENDPOINT_OUTPUT_TIMED_OUT
        ) from error
    if endpoint.startswith("http://127.0.0.1:"):
        return endpoint
    raise FixtureServerStartupError(FixtureServerStartupReason.ENDPOINT_OUTPUT_CLOSED)


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
