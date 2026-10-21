from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]
_DOCS: Final = _ROOT / "docs"
_DOC_PAGE_STEMS: Final = (
    "statistical-foundations",
    "measurement-and-summaries",
    "eligibility-and-comparability",
    "uncertainty-and-comparison",
    "decisions-and-limitations",
    "references-and-glossary",
)
_LESSON_NAMES: Final = (
    "01-overview.py",
    "02-collect.py",
    "03-summarize.py",
    "04-compare.py",
    "05-failures-and-ci.py",
    "06-statistical-foundations.py",
    "07-summary-and-eligibility.py",
    "08-bootstrap-and-decisions.py",
)


def _read(relative_path: Path) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_docs_index_contract(index: str) -> None:
    marker = ".. toctree::"
    assert marker in index, "documentation index must define a toctree"
    entries_list: list[str] = []
    for line in index.split(marker, maxsplit=1)[1].splitlines():
        if not line:
            continue
        if not line.startswith("   "):
            break
        entry = line.strip()
        if not entry.startswith(":"):
            entries_list.append(entry)
    entries = tuple(entries_list)
    assert entries == _DOC_PAGE_STEMS
    for page in _DOC_PAGE_STEMS:
        assert index.count(f":doc:`{page}`") == 1


def _assert_furo_configuration(conf: str, pyproject: str) -> None:
    required_conf = (
        'needs_sphinx = "9.1"',
        "extensions: list[str] = []",
        "nitpicky = True",
        'html_theme = "furo"',
        'html_static_path = ["_static"]',
        'html_css_files = ["custom.css"]',
    )
    assert all(setting in conf for setting in required_conf)
    docs_group = re.search(
        r'(?m)^docs = \[\n(?P<dependencies>(?:    "[^\n]*",\n)+)\]',
        pyproject,
    )
    assert docs_group is not None
    assert tuple(re.findall(r'"([^"]+)"', docs_group.group("dependencies"))) == (
        "furo==2025.12.19",
        "sphinx==9.1.1",
    )
    n999_paths = tuple(
        re.findall(r'^"([^"]+)" = \["N999"\]$', pyproject, flags=re.MULTILINE)
    )
    assert n999_paths == tuple(f"examples/{name}" for name in _LESSON_NAMES)
    base_dependencies = pyproject.split("[project.scripts]", maxsplit=1)[0]
    assert all(
        dependency not in base_dependencies
        for dependency in ("furo", "marimo", "sphinx")
    )


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


def test_root_navigation_links_to_docs_and_curriculum() -> None:
    # Given: the root README that introduces supported learning materials.
    readme = _read(Path("README.md"))

    # When: a developer looks for either learning path.

    # Then: the optional Furo site and Marimo curriculum have explicit entry points.
    assert "[Furo theory documentation](docs/index.rst)" in readme
    assert "[Marimo curriculum index](examples/README.md)" in readme


def test_docs_index_has_each_theory_page_once_in_navigation_order() -> None:
    # Given: the source for the Furo documentation landing page.
    index = _read(Path("docs/index.rst"))

    # When: its toctree and reading map are inspected.
    _assert_docs_index_contract(index)

    # Then: every linked source page exists for Sphinx to resolve.
    assert all((_DOCS / f"{page}.rst").is_file() for page in _DOC_PAGE_STEMS)


def test_docs_index_rejects_a_missing_toctree_page() -> None:
    # Given: an otherwise valid Furo landing page missing one canonical entry.
    incomplete_index = _read(Path("docs/index.rst")).replace(
        "   decisions-and-limitations\n", ""
    )

    # When: the navigation contract validates the altered source.

    # Then: it rejects the broken toctree before a documentation build can mask it.
    with pytest.raises(AssertionError):
        _assert_docs_index_contract(incomplete_index)


def test_all_sphinx_doc_references_resolve_to_known_sources() -> None:
    # Given: every theory source page and the index.
    sources = (
        _read(Path("docs/index.rst")),
        *(_read(Path("docs") / f"{page}.rst") for page in _DOC_PAGE_STEMS),
    )

    # When: every explicit Sphinx document reference is collected.
    references = tuple(
        reference for source in sources for reference in _doc_references(source)
    )

    # Then: each reference maps to one committed Sphinx source file.
    assert references
    assert all((_DOCS / f"{reference}.rst").is_file() for reference in references)


def test_furo_configuration_uses_locked_optional_dependencies() -> None:
    # Given: the Sphinx configuration and project dependency declaration.
    conf = _read(Path("docs/conf.py"))
    pyproject = _read(Path("pyproject.toml"))

    # When: the Furo build contract is checked.
    _assert_furo_configuration(conf, pyproject)

    # Then: the docs-only toolchain remains distinct from base dependencies.


def test_furo_configuration_rejects_a_different_theme() -> None:
    # Given: the project configuration with its Furo theme replaced.
    conf = _read(Path("docs/conf.py")).replace(
        'html_theme = "furo"', 'html_theme = "alabaster"'
    )

    # When: the Furo contract inspects the altered configuration.

    # Then: a different Sphinx theme is rejected.
    with pytest.raises(AssertionError):
        _assert_furo_configuration(conf, _read(Path("pyproject.toml")))


def test_furo_configuration_rejects_a_wrong_direct_pin() -> None:
    # Given: the project metadata with a noncanonical Furo pin.
    pyproject = _read(Path("pyproject.toml")).replace("furo==2025.12.19", "furo==0.0.0")

    # When: the Furo contract inspects the altered dependency group.

    # Then: the reproducible pin mismatch is rejected.
    with pytest.raises(AssertionError):
        _assert_furo_configuration(_read(Path("docs/conf.py")), pyproject)
