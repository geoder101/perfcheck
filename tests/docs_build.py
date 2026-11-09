from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from shutil import copytree, ignore_patterns, rmtree
from typing import Final

from tools.docs_inputs import docs_input_sha, lock_build

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


_MAX_CACHE_KEYS: Final = 5


def prune_cache(max_keys: int, active_marker: Path) -> None:
    """Reap the oldest cached renders, preserving readers and the newest builds."""
    if not _CACHE_DIR.is_dir():
        return
    entries = sorted(
        (child for child in _CACHE_DIR.iterdir() if child.is_dir()),
        key=lambda path: path.stat().st_mtime,
    )
    keep: set[Path] = set(entries[-max_keys:] if max_keys > 0 else [])
    keep.add(active_marker.parent)
    for stale in entries:
        if stale in keep or (stale / ".reading").is_file():
            continue
        rmtree(stale)


def ensure_built_docs(project: Path) -> subprocess.CompletedProcess[str] | None:
    """Reuse a cached build when inputs are unchanged, otherwise build and cache it.

    Renders into a content-addressed tree and returns the build result only when a
    fresh Sphinx render actually ran, so the caller can assert on it; returns
    ``None`` when an identical cached build was reused. Readers publish a marker
    before leaving the build lock so a concurrent worker never reaps or copies a
    half-written tree, then release the lock so many workers copy the cache at once.
    """
    key = docs_input_sha()
    key_dir = _CACHE_DIR / key
    cached_docs = key_dir / "docs"
    reading_marker = key_dir / ".reading"
    reuse_cached = False
    with lock_build():
        if not cached_docs.joinpath("_build/html/index.html").is_file():
            copy_docs_project(_SOURCE_ROOT, project)
            result = build_docs(project)
            if result.returncode != 0:
                return result
            if cached_docs.exists():
                rmtree(cached_docs)
            _ = copytree(
                project / "docs", cached_docs, ignore=ignore_patterns("__pycache__")
            )
        else:
            # Hit path: the built tree is already in place, so only this needs a copy.
            reuse_cached = True
        # Publish the tree before releasing the lock so prune never reaps it mid-copy.
        key_dir.mkdir(parents=True, exist_ok=True)
        _ = reading_marker.write_text(key, encoding="utf-8")
    # Copy the stable tree outside the lock so many workers hit the cache concurrently.
    if reuse_cached:
        _ = copytree(
            cached_docs, project / "docs", ignore=ignore_patterns("__pycache__")
        )
    prune_cache(_MAX_CACHE_KEYS, reading_marker)
    if reading_marker.is_file():
        reading_marker.unlink()
    return None


def assert_local_svg_urls(source: str) -> None:
    for match in re.finditer(r"url\s*\(([^)]*)\)", source, re.IGNORECASE):
        assert re.fullmatch(r"""(['"]?)#[^\s'"()]+\1""", match.group(1).strip())
