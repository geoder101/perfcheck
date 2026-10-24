from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import IO, TYPE_CHECKING, Literal, assert_never

import pytest

from perfcheck import cli_services, storage
from tests.cli_support import cli_policy, cli_run

if TYPE_CHECKING:
    from collections.abc import Generator

type Writer = Literal["artifact", "report"]
type Stage = Literal["write", "flush", "fsync", "link", "replace"]


@dataclass(frozen=True, slots=True)
class FailureCase:
    writer: Writer
    stage: Stage
    force: bool
    existing: bool


def filesystem_operations(stage: Stage, error: OSError) -> SimpleNamespace:
    def fsync(descriptor: int) -> None:
        if stage == "fsync":
            raise error
        os.fsync(descriptor)

    def link(source: Path, target: Path) -> None:
        if stage == "link":
            raise error
        os.link(source, target)

    return SimpleNamespace(fsync=fsync, link=link)


@contextmanager
def failing_filesystem(
    case: FailureCase, monkeypatch: pytest.MonkeyPatch
) -> Generator[OSError]:
    error = OSError("injected persistence failure")
    real_temporary = tempfile.NamedTemporaryFile

    def fail_write(_data: bytes) -> int:
        raise error

    def fail_flush() -> None:
        raise error

    def replace(_source: Path, _target: Path) -> Path:
        raise error

    @contextmanager
    def temporary(*, dir: Path, delete: bool) -> Generator[IO[bytes]]:  # noqa: A002
        with real_temporary(dir=dir, delete=delete) as stream:
            match case.stage:
                case "write":
                    # Leave actual partial bytes before simulating a write failure.
                    _ = stream.write(b"partial")
                    monkeypatch.setattr(stream, "write", fail_write)
                case "flush":
                    monkeypatch.setattr(stream, "flush", fail_flush)
                case "fsync" | "link" | "replace":
                    pass
                case _:
                    assert_never(case.stage)
            yield stream

    module = storage if case.writer == "artifact" else cli_services
    with monkeypatch.context() as patch:
        patch.setattr(module, "tempfile", SimpleNamespace(NamedTemporaryFile=temporary))
        patch.setattr(module, "os", filesystem_operations(case.stage, error))
        if case.stage == "replace":
            patch.setattr(Path, "replace", replace)
        yield error


def write_output(writer: Writer, path: Path, force: bool) -> None:
    match writer:
        case "artifact":
            storage.write_artifact(path, cli_run(cli_policy(), 1, 10.0), force=force)
        case "report":
            cli_services.write_report(path, b"new report", force=force)
        case _:
            assert_never(writer)


@pytest.mark.parametrize(
    "case",
    [
        FailureCase(writer, stage, force, existing)
        for writer in ("artifact", "report")
        for stage in ("write", "flush", "fsync", "link", "replace")
        for force in (False, True)
        for existing in (False, True)
        if (stage != "link" or not force) and (stage != "replace" or force)
    ],
)
def test_writer_cleans_temporary_and_preserves_destination_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: FailureCase
) -> None:
    # Given: a real destination and narrowly scoped failing filesystem operations.
    destination = tmp_path / "output.json"
    original = b"existing complete evidence\x00\n"
    if case.existing:
        _ = destination.write_bytes(original)
    # When: the selected persistence operation raises its original exception.
    with (
        failing_filesystem(case, monkeypatch) as error,
        pytest.raises(OSError, match="injected persistence failure") as caught,
    ):
        write_output(case.writer, destination, case.force)

    # Then: no temporary or partial output survives, and existing bytes are intact.
    assert caught.value is error
    assert set(tmp_path.iterdir()) == ({destination} if case.existing else set())
    if case.existing:
        assert destination.read_bytes() == original


@pytest.mark.parametrize("writer", ["artifact", "report"])
def test_writer_refuses_existing_destination_without_force(
    tmp_path: Path, writer: Writer
) -> None:
    # Given: an existing file which must never be overwritten implicitly.
    path = tmp_path / "output"
    _ = path.write_bytes(b"keep exactly")
    # When: a caller writes without replacement permission.
    with pytest.raises(FileExistsError):
        write_output(writer, path, force=False)
    # Then: the original and only the original remains.
    assert path.read_bytes() == b"keep exactly"
    assert set(tmp_path.iterdir()) == {path}


def test_report_preserves_write_error_when_cleanup_also_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an early write failure followed by a separate cleanup failure.
    cleanup_error = PermissionError("injected cleanup failure")

    def unlink(_path: Path, *, missing_ok: bool = False) -> None:
        del missing_ok
        raise cleanup_error

    # When: report cleanup cannot remove the partially written temporary file.
    with (
        failing_filesystem(
            FailureCase("report", "write", force=False, existing=False), monkeypatch
        ) as original,
        monkeypatch.context() as patch,
    ):
        patch.setattr(Path, "unlink", unlink)
        with pytest.raises(OSError, match="injected persistence failure") as caught:
            cli_services.write_report(tmp_path / "report", b"report", force=False)

    # Then: the primary write failure, not the cleanup failure, reaches the caller.
    assert caught.value is original
    assert not (tmp_path / "report").exists()


def test_report_preserves_publication_conflict_when_cleanup_also_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a real no-force publication conflict and a failing cleanup operation.
    destination = tmp_path / "report"
    _ = destination.write_bytes(b"keep exactly")
    conflicts: list[FileExistsError] = []
    cleanup_error = PermissionError("injected cleanup failure")

    def link(source: Path, target: Path) -> None:
        try:
            os.link(source, target)
        except FileExistsError as error:
            conflicts.append(error)
            raise

    def unlink(_path: Path, *, missing_ok: bool = False) -> None:
        del missing_ok
        raise cleanup_error

    # When: the atomic link refuses to overwrite and its temporary cleanup fails.
    with monkeypatch.context() as patch:
        patch.setattr(cli_services, "os", SimpleNamespace(fsync=os.fsync, link=link))
        patch.setattr(Path, "unlink", unlink)
        with pytest.raises(FileExistsError) as caught:
            cli_services.write_report(destination, b"new report", force=False)

    # Then: the identical publication error and the existing bytes are preserved.
    assert conflicts == [caught.value]
    assert conflicts[0] is caught.value
    assert destination.read_bytes() == b"keep exactly"


def test_report_propagates_cleanup_error_without_a_primary_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: successful forced publication followed by a failing cleanup operation.
    cleanup_error = PermissionError("injected cleanup failure")
    destination = tmp_path / "report"

    def unlink(_path: Path, *, missing_ok: bool = False) -> None:
        del missing_ok
        raise cleanup_error

    # When: cleanup is the only failing operation.
    with monkeypatch.context() as patch:
        patch.setattr(Path, "unlink", unlink)
        with pytest.raises(PermissionError) as caught:
            cli_services.write_report(destination, b"complete report", force=True)

    # Then: cleanup failures are not silently suppressed on the successful path.
    assert caught.value is cleanup_error
    assert destination.read_bytes() == b"complete report"
