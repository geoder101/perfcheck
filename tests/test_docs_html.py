from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Final, override
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET

import pytest

from tests.docs_build import assert_local_svg_urls

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
        self.math_images: list[tuple[str, str]] = []
        self.images: list[tuple[str, str]] = []
        self.objects: list[tuple[str, str]] = []
        self.scripts: list[str] = []
        self.feed(source)

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.links.extend(value for key, value in attrs if key == "href" and value)
        attributes = dict(attrs)
        if tag == "object":
            self.objects.append(
                (attributes.get("data") or "", attributes.get("type") or "")
            )
        if tag == "img":
            self.images.append(
                (attributes.get("src") or "", attributes.get("alt") or "")
            )
        if tag == "img" and "math" in (attributes.get("class") or "").split():
            self.math_images.append(
                (attributes.get("src") or "", attributes.get("alt") or "")
            )
        if tag == "script" and (src := attributes.get("src")):
            self.scripts.append(src)

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
    assert all(
        destination in page.links
        for destination in (
            "explanation/learning-paths.html",
            "tutorials/first-comparison.html",
            "tutorials/performance-verification-case-study.html",
        )
    )


def test_landing_page_explains_evidence_actors_and_decisions(built_docs: Path) -> None:
    # Given: the rendered introduction, not its source markup or diagram labels.
    page = _Page((built_docs / "_build/html/index.html").read_text(encoding="utf-8"))
    # When: readers access the textual workflow equivalent.
    text = " ".join(" ".join(page.text).split()).lower()
    # Then: purpose, actors, evidence transformations and outcomes are discoverable.
    assert all(
        concept in text
        for concept in (
            "repeated measurements",
            "inspectable",
            "investigation",
            "benchmark operator",
            "prometheus",
            "timestamped",
            "configured suite",
            "portable raw",
            "eligibility",
            "per-run scalar",
            "baseline and current",
            "comparable",
            "policy configuration",
            "json",
            "markdown",
            "pass",
            "fail",
            "inconclusive",
            "engineer",
            "ci",
        )
    )
    assert "raw-run inputs" in text
    assert "both cohorts" in text
    assert "documentation and lessons keep" not in text


def test_landing_workflow_object_is_accessible_and_self_contained(
    built_docs: Path,
) -> None:
    # Given: the built page and its locally published assets.
    html = built_docs / "_build/html"
    page = _Page((html / "index.html").read_text(encoding="utf-8"))
    # When: the extension's generated object is resolved like a browser resource.
    illustrations = [(src, kind) for src, kind in page.objects if "mermaid-" in src]
    # Then: accessible fallback text accompanies an in-tree SVG, not client JS.
    assert len(illustrations) == 1
    source, kind = illustrations[0]
    assert kind == "image/svg+xml"
    content = (html / "index.html").read_text(encoding="utf-8")
    fallback = re.search(r"<object\b[^>]*>(.*?)</object>", content, re.DOTALL)
    assert fallback
    assert all(
        word in fallback.group(1).lower() for word in ("workflow", "policy", "report")
    )
    assert 'class="mermaid"' not in content
    assert "mermaid.esm" not in content
    assert "cdn.jsdelivr.net" not in content
    assert not any("mermaid" in script or "d3" in script for script in page.scripts)
    assert not urlsplit(source).scheme
    assert not urlsplit(source).netloc
    image = (html / unquote(source)).resolve()
    assert image.is_relative_to(html.resolve())
    assert image.suffix == ".svg"
    svg = image.read_text(encoding="utf-8")
    root = ET.fromstring(svg)  # noqa: S314 - trusted, repository-owned SVG.
    namespace = {"svg": "http://www.w3.org/2000/svg"}
    assert root.findtext("svg:title", namespaces=namespace)
    assert root.findtext("svg:desc", namespaces=namespace)
    assert root.get("aria-labelledby")
    assert all(
        label in " ".join(root.itertext()).lower()
        for label in (
            "collect",
            "summarize",
            "compare",
            "prometheus",
            "policy",
            "baseline",
            "current",
            "raw",
            "eligibility",
            "scalar",
            "json",
            "markdown",
            "pass",
            "fail",
            "inconclusive",
            "engineer",
            "ci",
        )
    )
    assert not root.findall(".//svg:script", namespace)
    assert not root.findall(".//svg:foreignObject", namespace)
    for element in root.iter():
        for name, value in element.attrib.items():
            if name.endswith("href") or name == "src":
                assert value.startswith("#")
    assert_local_svg_urls(svg)
    assert "@import" not in svg


@pytest.mark.parametrize(
    "document",
    ["probability-and-distributions", "inference-and-power", "multiple-testing"],
)
def test_equations_when_built_use_local_svg_without_remote_scripts(
    document: str, built_docs: Path
) -> None:
    # Given: a fresh mathematical chapter, including inline and display equations.
    html = built_docs / "_build/html"
    path = html / "explanation" / f"{document}.html"
    # When: its rendered equation images and script requirements are parsed.
    page = _Page(path.read_text(encoding="utf-8"))
    # Then: equations have real local SVG glyphs and TeX alternatives, not a CDN.
    assert page.math_images
    assert all(not urlsplit(script).scheme for script in page.scripts)
    for source, alternative in page.math_images:
        assert source
        assert alternative
        assert not urlsplit(source).scheme
        image = (path.parent / source).resolve()
        assert image.is_relative_to(html.resolve())
        assert image.suffix == ".svg"
        svg = image.read_text(encoding="utf-8")
        assert "<svg" in svg
        assert "<path" in svg
    assert "\\[" not in "".join(page.text)
    assert "\\(" not in "".join(page.text)
