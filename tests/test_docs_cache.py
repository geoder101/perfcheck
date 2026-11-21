"""Unit coverage for the content-addressed documentation render cache.

These tests exercise the orchestration in :mod:`tests.docs_build` (caching,
reader-marker cleanup, and prune) and the shared cross-process lock without
running a real Sphinx render.
"""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest
from tools import docs_inputs

from tests import docs_build

if TYPE_CHECKING:
    from pathlib import Path


class _FakeResult:
    """Minimal stand-in for ``subprocess.CompletedProcess`` with a return code."""

    returncode: int

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the content cache at an isolated directory."""
    monkeypatch.setattr(docs_build, "_CACHE_DIR", tmp_path / "cache")
    return tmp_path / "cache"


def test_prune_keeps_newest_keys_and_reaps_older(cache_dir: Path) -> None:
    # Given: four cached render trees created in lexical order with distinct mtimes.
    for index in range(4):
        tree = cache_dir / f"key-{index:02d}"
        (tree / "docs").mkdir(parents=True, exist_ok=True)
        _ = (tree / "docs" / "index.html").write_text(str(index), encoding="utf-8")
        os.utime(tree, (1_000_000 + index, 1_000_000 + index))
    # When: only the newest two are requested to survive a prune.
    docs_build.prune_cache(2, active_marker=cache_dir / "active" / ".reading")
    # Then: the newest entries remain, older ones are reaped.
    assert sorted(child.name for child in cache_dir.iterdir()) == ["key-02", "key-03"]


def test_prune_preserves_reader_marked_cache(cache_dir: Path) -> None:
    # Given: an old tree another worker is actively copying, plus newer trees.
    active = cache_dir / "active"
    (active / "docs").mkdir(parents=True, exist_ok=True)
    reader = active / ".reading-reader"
    _ = reader.write_text("reader", encoding="utf-8")
    for index in range(3):
        tree = cache_dir / f"old-{index:02d}"
        (tree / "docs").mkdir(parents=True, exist_ok=True)
        _ = (tree / "docs" / "index.html").write_text(str(index), encoding="utf-8")
        os.utime(tree, (1_000_000 + index, 1_000_000 + index))
    os.utime(active, (1_000_000, 1_000_000))
    # When: pruning with the active reader flagged and only two newest kept.
    docs_build.prune_cache(2, active_marker=cache_dir / "elsewhere" / ".reading")
    # Then: the marked reader survives even though it is beyond the newest window.
    assert reader.is_file()
    assert sorted(child.name for child in cache_dir.iterdir()) == [
        "active",
        "old-01",
        "old-02",
    ]


def test_built_docs_caches_then_reuses_without_rebuilding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(docs_build, "_CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(docs_build, "docs_input_sha", lambda: "content-key")

    calls = {"build": 0}

    def fake_copy(_source: Path, destination: Path) -> None:
        (destination / "docs").mkdir(parents=True, exist_ok=True)

    def fake_build(project: Path) -> _FakeResult:
        calls["build"] += 1
        build = project / "docs" / "_build" / "html"
        build.mkdir(parents=True, exist_ok=True)
        _ = (build / "index.html").write_text("<html>", encoding="utf-8")
        return _FakeResult(0)

    monkeypatch.setattr(docs_build, "copy_docs_project", fake_copy)
    monkeypatch.setattr(docs_build, "build_docs", fake_build)

    # When: a worker requests a build on a cold cache.
    worker = tmp_path / "worker"
    result = docs_build.ensure_built_docs(worker)
    # Then: it renders once, stores the tree, cleans the publish marker.
    assert result is None
    assert calls["build"] == 1
    cached = tmp_path / "cache" / "content-key" / "docs"
    assert (cached / "_build" / "html" / "index.html").is_file()
    assert not any((tmp_path / "cache" / "content-key").glob(".reading-*"))
    assert (worker / "docs" / "_build" / "html" / "index.html").is_file()

    # When: a second worker requests the same inputs.
    worker2 = tmp_path / "worker2"
    result = docs_build.ensure_built_docs(worker2)
    # Then: the cached render is reused without rendering again.
    assert result is None
    assert calls["build"] == 1
    assert (worker2 / "docs" / "_build" / "html" / "index.html").is_file()


def test_lock_build_excludes_second_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a per-test lock file (Unix only; the helper is a no-op on Windows).
    if sys.platform == "win32":
        pytest.skip("fcntl cross-process locking is Unix-only")
    import fcntl  # noqa: PLC0415 - the Unix-specific lock probe only.

    monkeypatch.setattr(docs_inputs, "_LOCK_PATH", tmp_path / "build.lock")
    # When: a worker holds the shared docs-build lock.
    with (
        docs_inputs.lock_build(),
        (tmp_path / "build.lock").open("w") as conflict,
        pytest.raises(BlockingIOError),
    ):
        # Then: a non-blocking second acquisition conflicts and raises.
        fcntl.flock(conflict, fcntl.LOCK_EX | fcntl.LOCK_NB)


@pytest.mark.parametrize(
    "relative",
    [
        "docs/_static/custom.css",
        "docs/_static/landing.svg",
        "uv.lock",
        "pyproject.toml",
        "tools/docs/package.json",
        "tools/docs/package-lock.json",
    ],
)
def test_render_input_changes_invalidate_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    # Given: an authored asset or dependency input in an isolated project.
    monkeypatch.setattr(docs_inputs, "docs_root", lambda: tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    _ = path.write_text("old", encoding="utf-8")
    previous = docs_inputs.docs_input_sha()

    # When: its contents change without changing its name.
    _ = path.write_text("new", encoding="utf-8")

    # Then: the cached render becomes ineligible for reuse.
    assert docs_inputs.docs_input_sha() != previous


def test_generated_docs_do_not_invalidate_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: an isolated project's render fingerprint.
    monkeypatch.setattr(docs_inputs, "docs_root", lambda: tmp_path)
    previous = docs_inputs.docs_input_sha()

    # When: Sphinx and AutoAPI write generated output.
    for relative in ("docs/_build/output.rst", "docs/reference/api/index.rst"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("generated", encoding="utf-8")

    # Then: generated files are not render inputs.
    assert docs_inputs.docs_input_sha() == previous
