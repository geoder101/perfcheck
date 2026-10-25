"""Validate usable local coverage HTML without executing its content."""

from __future__ import annotations

from html.parser import HTMLParser
from typing import TYPE_CHECKING, override
from urllib.parse import unquote, urlsplit

from tools.quality_evidence_models import require

if TYPE_CHECKING:
    from pathlib import Path


class CoverageHtml(HTMLParser):
    """Collect document markers and relative asset/page references."""

    def __init__(self) -> None:
        """Initialize the mutable parser accumulator."""
        super().__init__(convert_charrefs=True)
        self.has_html: bool = False
        self.has_title: bool = False
        self.references: list[str] = []

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Record references for local-only path and existence checks."""
        self.has_html = self.has_html or tag == "html"
        self.has_title = self.has_title or tag == "title"
        self.references.extend(
            value
            for name, value in attrs
            if name in {"href", "src"} and value is not None
        )


def validate_html(root: Path, started_ns: int, finished_ns: int) -> None:
    """Require fresh coverage documents and all referenced local assets/pages."""
    require(root.is_dir())
    for directory, _, files in root.walk(on_error=_scan_error):
        for name in files:
            path = directory / name
            require(started_ns <= path.stat().st_mtime_ns <= finished_ns)
            if path.suffix == ".html":
                text = path.read_text(encoding="utf-8")
                parser = CoverageHtml()
                parser.feed(text)
                require(parser.has_html and parser.has_title)
                require("coverage.py" in text)
                for reference in parser.references:
                    parsed = urlsplit(reference)
                    if parsed.scheme or parsed.netloc or not parsed.path:
                        continue
                    target = (path.parent / unquote(parsed.path)).resolve()
                    require(target.is_relative_to(root.resolve()) and target.is_file())


def _scan_error(error: OSError) -> None:
    raise error
