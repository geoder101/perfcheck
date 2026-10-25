"""Bounded Unix subprocess execution for the optional mutation experiment."""

from __future__ import annotations

import os
import signal
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Generator
    from pathlib import Path
    from types import FrameType


def _interrupt(signum: int, _frame: FrameType | None) -> None:
    raise InterruptedError(signum, "mutation runner terminated")


@contextmanager
def _catch_termination() -> Generator[None]:
    previous = signal.signal(signal.SIGTERM, _interrupt)
    try:
        yield
    finally:
        _ = signal.signal(signal.SIGTERM, previous)


@dataclass(frozen=True, slots=True)
class Command:
    """An explicit executable invocation in an isolated working directory."""

    argv: tuple[str, ...]
    cwd: Path
    env: dict[str, str] | None = None


@dataclass(frozen=True, slots=True)
class ChildResult:
    """Preserve the distinction between child exit and wall-budget exhaustion."""

    returncode: int
    timed_out: bool


def run_child(command: Command, log: Path, budget: float) -> ChildResult:
    """Kill the entire new process group, including descendants, on every exit."""
    with (
        _catch_termination(),
        log.open("x") as output,
        subprocess.Popen(  # noqa: S603 - internal explicit argv, never shell input
            command.argv,
            cwd=command.cwd,
            env=command.env,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        ) as child,
    ):
        timed_out = False
        try:
            code = child.wait(timeout=budget)
        except subprocess.TimeoutExpired:
            timed_out = True
            code = -signal.SIGKILL
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                # The group already exited normally; there are no descendants.
                code = child.wait()
            _ = child.wait()
    return ChildResult(code, timed_out)
