"""Content hashing for documentation inputs shared by tests and the docs gate."""

from __future__ import annotations

import errno
import hashlib
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Generator
    from typing import BinaryIO

_ROOT: Final = Path(__file__).resolve().parents[1]

_DOC_INPUT_GLOBS: Final = (
    "src/**/*.py",
    "docs/**/*.rst",
    "docs/conf.py",
    "docs/_templates/**",
    "docs/_static/**",
    "pyproject.toml",
    "uv.lock",
    "tools/mermaid.py",
    "tools/docs_inputs.py",
    "tools/docs_gate.py",
    "tools/docs/package*.json",
    "tools/docs/puppeteer*.json",
)


def docs_root() -> Path:
    """Return the repository root that owns the documentation sources."""
    return _ROOT


def docs_input_sha() -> str:
    """Hash every input that affects a documentation render, in lexical order."""
    hasher = hashlib.sha256()
    for pattern in _DOC_INPUT_GLOBS:
        for path in sorted(docs_root().glob(pattern)):
            relative = path.relative_to(docs_root())
            if (
                not path.is_file()
                or "_build" in relative.parts
                or relative.is_relative_to("docs/reference/api")
            ):
                continue
            hasher.update(path.relative_to(docs_root()).as_posix().encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
    return hasher.hexdigest()


_LOCK_PATH: Final = _ROOT / ".docs_build.lock"


@contextmanager
def lock_build() -> Generator[None]:
    """Serialize concurrent docs renders across processes on every supported OS."""
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        with _LOCK_PATH.open("a+b") as handle, _windows_lock(handle):
            yield
        return
    handle = _LOCK_PATH.open("w")
    import fcntl  # noqa: PLC0415 - Unix-only; avoided on Windows

    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


@contextmanager
def _windows_lock(handle: BinaryIO) -> Generator[None]:
    import msvcrt  # noqa: PLC0415 - available only on Windows.

    if handle.seek(0, 2) == 0:
        _ = handle.write(b"\0")
        handle.flush()
    _ = handle.seek(0)
    while True:
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            break
        except OSError as error:
            if error.errno not in {errno.EACCES, errno.EDEADLK}:
                raise
            time.sleep(0.1)
    try:
        yield
    finally:
        _ = handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
