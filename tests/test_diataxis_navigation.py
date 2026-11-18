from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]
_DOCS: Final = _ROOT / "docs"
_BLOB_PREFIX: Final = "https://github.com/geoder101/perfcheck/blob/main/"
_SECTION_DOCUMENTS: Final = (
    "tutorials/index",
    "how-to/index",
    "reference/index",
    "explanation/index",
)
_SECTION_LABELS: Final = (
    "Tutorials",
    "How-to guides",
    "Reference",
    "Explanation",
)
_THEORY_PAGE_STEMS: Final = (
    "learning-paths",
    "statistical-foundations",
    "probability-and-distributions",
    "experimental-design",
    "measurement-and-summaries",
    "eligibility-and-comparability",
    "inference-and-power",
    "multiple-testing",
    "uncertainty-and-comparison",
    "decisions-and-limitations",
    "plain-python-mechanics",
    "comparative-methods",
)
_THEORY_DOCUMENTS: Final = (
    "explanation/learning-paths",
    "explanation/statistical-foundations",
    "explanation/probability-and-distributions",
    "explanation/experimental-design",
    "explanation/measurement-and-summaries",
    "explanation/eligibility-and-comparability",
    "explanation/inference-and-power",
    "explanation/multiple-testing",
    "explanation/uncertainty-and-comparison",
    "explanation/decisions-and-limitations",
    "explanation/plain-python-mechanics",
    "explanation/comparative-methods",
)
_SECTION_PAGES: Final = (
    ("tutorials", ("first-comparison", "performance-verification-case-study")),
    (
        "how-to",
        (
            "collect-a-run",
            "prometheus-authentication",
            "summarize-evidence",
            "compare-cohorts",
            "ci-regression-gate",
        ),
    ),
    ("reference", ("cli", "policy-and-artifacts", "glossary", "api/index")),
    ("explanation", _THEORY_PAGE_STEMS),
)


def _read(relative_path: Path) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _toctree_entries(source: str) -> tuple[str, ...]:
    marker = ".. toctree::"
    assert marker in source, "documentation index must define a toctree"
    entries_list: list[str] = []
    for line in source.split(marker, maxsplit=1)[1].splitlines():
        if not line:
            continue
        if not line.startswith("   "):
            break
        entry = line.strip()
        if not entry.startswith(":"):
            entries_list.append(entry)
    return tuple(entries_list)


def _document_source(source_path: Path, document: str) -> Path:
    source_directory = _DOCS if document.startswith("/") else source_path.parent
    return source_directory / f"{document.lstrip('/')}.rst"


def _assert_navigation_contract(root_index: str, explanation_index: str) -> None:
    assert _toctree_entries(root_index) == _SECTION_DOCUMENTS
    assert _toctree_entries(explanation_index) == _THEORY_PAGE_STEMS


def _doc_references(source: str) -> tuple[str, ...]:
    references: list[str] = []
    for source_line in source.splitlines():
        remaining = source_line
        while ":doc:`" in remaining:
            _, _, after_marker = remaining.partition(":doc:`")
            raw_reference, _, remaining = after_marker.partition("`")
            references.append(
                raw_reference.rsplit("<", maxsplit=1)[-1].rstrip(">").strip()
            )
    return tuple(references)


def test_root_navigation_exposes_workflow_and_four_diataxis_sections() -> None:
    # Given: the source for the Furo documentation landing page.
    index = _read(Path("docs/index.rst"))

    # When: a first-time visitor reaches the workflow section and section links.
    _, _, workflow_section = index.partition("From observations to a decision\n")
    workflow_section, _, _ = workflow_section.partition("\nScope\n")

    # Then: the workflow names each command and navigation has four destinations.
    assert all(
        f"``{command}``" in workflow_section
        for command in ("collect", "summarize", "compare")
    )
    assert _toctree_entries(index) == _SECTION_DOCUMENTS


def test_section_indexes_define_the_four_diataxis_labels() -> None:
    # Given: the section index sources reached from the documentation landing page.
    section_indexes = tuple(
        _read(Path("docs") / f"{document}.rst") for document in _SECTION_DOCUMENTS
    )

    # When: their rendered document titles are collected.
    titles = tuple(source.splitlines()[0] for source in section_indexes)

    # Then: each Diataxis section is present with its canonical reader-facing label.
    assert titles == _SECTION_LABELS


def test_moved_theory_sources_have_one_explanation_owner_without_root_sources() -> None:
    # Given: the root and Explanation navigation sources.
    root_index_path = _DOCS / "index.rst"
    explanation_index_path = _DOCS / "explanation/index.rst"
    root_index = _read(root_index_path.relative_to(_ROOT))
    explanation_index = _read(explanation_index_path.relative_to(_ROOT))

    # When: their toctree entries are resolved from each index location.
    destinations = (
        *(
            _document_source(root_index_path, entry)
            for entry in _toctree_entries(root_index)
        ),
        *(
            _document_source(explanation_index_path, entry)
            for entry in _toctree_entries(explanation_index)
        ),
    )

    # Then: each current page has exactly one intended owner and no legacy root remains.
    expected_destinations = (
        *(_DOCS / f"{document}.rst" for document in _SECTION_DOCUMENTS),
        *(_DOCS / f"{document}.rst" for document in _THEORY_DOCUMENTS),
    )
    assert destinations == expected_destinations
    assert len(destinations) == len(set(destinations))
    assert all(destination.is_file() for destination in destinations)
    assert all(not (_DOCS / f"{page}.rst").exists() for page in _THEORY_PAGE_STEMS)


def test_navigation_contract_rejects_a_missing_explanation_page() -> None:
    # Given: an otherwise valid Explanation index missing one migrated chapter.
    root_index = _read(Path("docs/index.rst"))
    incomplete_explanation_index = _read(Path("docs/explanation/index.rst")).replace(
        "   decisions-and-limitations\n", ""
    )

    # When: the navigation contract validates the altered source.

    # Then: it rejects the broken toctree before a documentation build can mask it.
    with pytest.raises(AssertionError):
        _assert_navigation_contract(root_index, incomplete_explanation_index)


def test_all_sphinx_doc_references_resolve_to_known_sources() -> None:
    # Given: every Diataxis index and migrated Explanation source page.
    source_paths = tuple(
        path
        for path in _DOCS.rglob("*.rst")
        if not {"_build", "_templates", "api"}.intersection(path.parts)
    )

    # When: every explicit Sphinx document reference is collected and resolved.
    references = tuple(
        (source_path, reference)
        for source_path in source_paths
        for reference in _doc_references(_read(source_path.relative_to(_ROOT)))
    )

    # Then: each reference maps to one committed Sphinx source file in its context.
    assert references
    assert all(
        _document_source(source_path, reference).is_file()
        for source_path, reference in references
    )


@pytest.mark.parametrize(("section", "pages"), _SECTION_PAGES)
def test_section_navigation_covers_every_page_in_order(
    section: str, pages: tuple[str, ...], built_docs: Path
) -> None:
    # Given: one canonical Diataxis section index.
    source = _read(Path("docs") / section / "index.rst")

    # When: its structured toctree destinations are collected.
    entries = _toctree_entries(source)

    # Then: every leaf has one ordered owner, including the generated API entry.
    assert entries == pages
    assert all((built_docs / section / f"{page}.rst").is_file() for page in entries)


@pytest.mark.parametrize("section", _SECTION_DOCUMENTS)
def test_navigation_contract_rejects_a_missing_section(section: str) -> None:
    # Given: the landing page with one Diataxis destination removed.
    source = _read(Path("docs/index.rst")).replace(f"   {section}\n", "")

    # When: the same navigation contract inspects the incomplete landing page.
    # Then: other valid links cannot hide the missing section.
    with pytest.raises(AssertionError):
        _assert_navigation_contract(source, _read(Path("docs/explanation/index.rst")))


def test_committed_document_manifest_has_no_unowned_or_legacy_pages() -> None:
    # Given: the complete explicit Diataxis navigation contract.
    expected = {
        "index.rst",
        *(f"{section}/index.rst" for section, _ in _SECTION_PAGES),
        *(
            f"{section}/{page}.rst"
            for section, pages in _SECTION_PAGES
            for page in pages
            if page != "api/index"
        ),
    }

    # When: all non-generated documentation sources are enumerated.
    actual = {
        path.relative_to(_DOCS).as_posix()
        for path in _DOCS.rglob("*.rst")
        if not {"_build", "_templates", "api"}.intersection(path.parts)
    }

    # Then: no stale six-page manifest or unlinked root-level theory page survives.
    assert actual == expected


def _resolve_repo_path(source: Path, link: str) -> Path:
    """Resolve an in-repo ``<path>_`` link to a repository file path.

    ``blob/main`` external links map to files in the checkout under the resolved
    repository root; relative links resolve against their source page.
    """
    if link.startswith(_BLOB_PREFIX):
        return _ROOT / link[len(_BLOB_PREFIX) :]
    return source.parent / link


def test_all_rst_blob_and_relative_links_resolve() -> None:
    # Given: every authored RST page, excluding generated API and HTML outputs.
    sources = tuple(
        path
        for path in _DOCS.rglob("*.rst")
        if not {"_build", "_templates", "api"}.intersection(path.parts)
    )

    # When: in-repo download links (blob/main or relative) are collected.
    destinations = tuple(
        (source, _resolve_repo_path(source, match.group(1)))
        for source in sources
        for match in re.finditer(r"<([^<>]+)>`", source.read_text(encoding="utf-8"))
        if match.group(1).startswith(_BLOB_PREFIX) or match.group(1).startswith(".")
    )

    # Then: lesson and fixture downloads are real files, not just convincing labels.
    assert destinations, "Expected in-repo documentation links in authored RST sources."
    broken = [
        f"{source.relative_to(_ROOT)} -> {resolved}"
        for source, resolved in destinations
        if not resolved.is_file()
    ]
    assert not broken, (
        "In-repo documentation links resolve to missing files:\n" + "\n".join(broken)
    )
