"""Content hashing for documentation inputs shared by tests and the docs gate."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

_ROOT: Final = Path(__file__).resolve().parents[1]

_DOC_INPUT_GLOBS: Final = (
    "src/**/*.py",
    "docs/**/*.rst",
    "docs/conf.py",
    "docs/_templates/**",
    "tools/mermaid.py",
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
            if not path.is_file():
                continue
            hasher.update(path.relative_to(docs_root()).as_posix().encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(path.read_bytes())
            hasher.update(b"\0")
    return hasher.hexdigest()
