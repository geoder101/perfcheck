from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Final, override
from urllib.parse import unquote, urlsplit

import pytest

_DOCS: Final = Path(__file__).parents[1] / "docs"
_AUTHORED_PAGES: Final = tuple(
    source.relative_to(_DOCS).with_suffix(".html")
    for source in sorted(_DOCS.rglob("*.rst"))
    if not {"_build", "_templates", "api"}.intersection(source.parts)
)


class _Page(HTMLParser):
    """Accumulate rendered links and text while the HTML parser feeds events."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self.text: list[str] = []
        self.feed(source)

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)

    @override
    def handle_data(self, data: str) -> None:
        self.text.append(data)


@pytest.mark.parametrize("relative_path", _AUTHORED_PAGES)
def test_rendered_documentation_links_resolve_within_site(
    relative_path: Path, built_docs: Path
) -> None:
    # Given: one freshly built authored document with Furo navigation and downloads.
    html = built_docs / "_build/html"
    path = html / relative_path
    page = _Page(path.read_text(encoding="utf-8"))

    # When: actual HTML anchor destinations are resolved as a browser would.
    local_paths = tuple(
        (path.parent / unquote(urlsplit(link).path)).resolve()
        for link in page.links
        if not urlsplit(link).scheme
        and not urlsplit(link).netloc
        and urlsplit(link).path
    )

    # Then: no source-only lesson link escapes the built site or yields a 404.
    assert local_paths
    assert all(target.is_relative_to(html.resolve()) for target in local_paths)
    assert all(target.is_file() for target in local_paths)


def test_rendered_landing_page_exposes_project_workflow_and_four_paths(
    built_docs: Path,
) -> None:
    # Given: the built landing page visitors actually receive.
    page = _Page((built_docs / "_build/html/index.html").read_text(encoding="utf-8"))

    # When: its rendered text and anchor targets are collected.
    text = " ".join(" ".join(page.text).split())

    # Then: the project-first workflow and all four Diataxis sections survive build.
    assert "perfcheck documentation" in text
    assert all(command in text for command in ("collect", "summarize", "compare"))
    assert all(
        f"{section}/index.html" in page.links
        for section in ("tutorials", "how-to", "reference", "explanation")
    )
