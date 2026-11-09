from __future__ import annotations

import os
import re
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from shutil import copytree, ignore_patterns, rmtree
from typing import TYPE_CHECKING, Final

from tools.docs_inputs import docs_input_sha

if TYPE_CHECKING:
    from collections.abc import Generator

_CACHE_DIR: Final = Path(__file__).resolve().parents[1] / ".pytest_docs_cache"


def copy_docs_project(source: Path, destination: Path) -> None:
    for directory in ("docs", "src", "examples", "tests", "tools"):
        _ = copytree(
            source / directory,
            destination / directory,
            ignore=ignore_patterns(
                "_build", "api", "__pycache__", "node_modules", ".cache"
            ),
        )


def build_docs(project: Path) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).parents[1]
    environment = os.environ.copy()
    cli = root / "tools/docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    if cli.is_file():
        _ = environment.setdefault("PERFCHECK_MERMAID_CLI", str(cli))
    return subprocess.run(  # noqa: S603 - fixed documentation build command.
        [  # noqa: S607 - uv is the repository's required environment manager.
            "uv",
            "run",
            "--group",
            "docs",
            "sphinx-build",
            "-b",
            "html",
            str(project / "docs"),
            str(project / "docs/_build/html"),
            "-E",
            "-a",
            "-W",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


_SOURCE_ROOT: Final = Path(__file__).resolve().parents[1]


@contextmanager
def _lock_build() -> Generator[None]:
    """Serialize first-time renders across parallel workers on Unix."""
    if sys.platform == "win32":
        yield
        return
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    handle = _CACHE_DIR.joinpath(".build.lock").open("w")
    import fcntl  # noqa: PLC0415 - Unix-only; avoided on Windows

    try:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def ensure_built_docs(project: Path) -> subprocess.CompletedProcess[str] | None:
    """Reuse a cached build when inputs are unchanged, otherwise build and cache it.

    Copies the full cached tree on a hit; otherwise copies the authored sources,
    renders them, and stores the result. Returns the build result only when a
    fresh Sphinx render actually ran, so the caller can assert on it; returns
    ``None`` when an identical cached build was reused. A build lock serializes
    first-time renders across parallel workers.
    """
    key = docs_input_sha()
    cached_docs = _CACHE_DIR / key / "docs"
    # Hold the lock across the whole check-then-build section so parallel workers
    # never copy a cache while another worker is rmtree-ing and repopulating it.
    with _lock_build():
        if cached_docs.joinpath("_build/html/index.html").is_file():
            _ = copytree(
                cached_docs, project / "docs", ignore=ignore_patterns("__pycache__")
            )
            return None
        copy_docs_project(_SOURCE_ROOT, project)
        result = build_docs(project)
        if result.returncode != 0:
            return result
        if cached_docs.exists():
            rmtree(cached_docs)
        _ = copytree(
            project / "docs", cached_docs, ignore=ignore_patterns("__pycache__")
        )
    return None


def assert_local_svg_urls(source: str) -> None:
    for match in re.finditer(r"url\s*\(([^)]*)\)", source, re.IGNORECASE):
        assert re.fullmatch(r"""(['"]?)#[^\s'"()]+\1""", match.group(1).strip())
