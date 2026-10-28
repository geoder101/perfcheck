from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]
_DOCS: Final = _ROOT / "docs"
_SOURCE: Final = _ROOT / "src"
_REFERENCE: Final = _DOCS / "reference"
_STATIC_REFERENCE_PAGES: Final = (
    "cli",
    "policy-and-artifacts",
    "glossary",
)
_AUTOAPI_OPTIONS: Final = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]
_SOURCE_EXCLUSION_REASONS: Final = (
    "AGENTS.md is repository guidance, not a Python module",
    "src/README.md is the source guide, not a Python module",
    "__pycache__ bytecode is generated, not source",
)


def _read(relative_path: Path) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _toctree_entries(source: str) -> tuple[str, ...]:
    marker = ".. toctree::"
    assert marker in source, "documentation index must define a toctree"
    entries: list[str] = []
    for line in source.split(marker, maxsplit=1)[1].splitlines():
        if not line:
            continue
        if not line.startswith("   "):
            break
        entry = line.strip()
        if not entry.startswith(":"):
            entries.append(entry)
    return tuple(entries)


def _source_modules() -> tuple[str, ...]:
    return tuple(
        _module_name(path)
        for path in sorted(_SOURCE.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def _module_name(path: Path) -> str:
    relative = path.relative_to(_SOURCE).with_suffix("")
    module_parts = (
        relative.parts[:-1] if relative.name == "__init__" else relative.parts
    )
    return ".".join(module_parts)


def _expected_generated_pages(docs: Path) -> tuple[Path, ...]:
    return tuple(
        docs.joinpath("reference/api", *module.split("."), "index.rst")
        for module in _source_modules()
    )


def _excluded_source_paths() -> tuple[Path, ...]:
    return tuple(
        path.relative_to(_SOURCE)
        for path in _SOURCE.rglob("*")
        if path.is_file() and path.suffix != ".py"
    )


def _git(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed Git inspection commands.
        ["git", *arguments],  # noqa: S607 - fixed Git inspection commands.
        cwd=_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def test_reference_contract_covers_source_manifest_and_navigation(
    built_docs: Path,
) -> None:
    # Given: the committed docs configuration, source modules, and Reference tree.
    pyproject = _read(Path("pyproject.toml"))
    conf = _read(Path("docs/conf.py"))
    reference_index = _read(Path("docs/reference/index.rst"))
    static_pages = tuple(
        _read(Path("docs/reference") / f"{page}.rst")
        for page in _STATIC_REFERENCE_PAGES
    )

    # When: the generated-reference contract is derived from the source tree.
    modules = _source_modules()
    generated_pages = _expected_generated_pages(built_docs)
    api_links = tuple(
        source_path
        for source_path in _DOCS.rglob("*.rst")
        if ".. toctree::" in source_path.read_text(encoding="utf-8")
        and "api/index" in _toctree_entries(source_path.read_text(encoding="utf-8"))
    )

    # Then: all source modules are covered without curated exclusions or owners.
    assert '"sphinx-autoapi==3.8.1",' in pyproject
    assert all(
        f'"{extension}"' in conf
        for extension in (
            "autoapi.extension",
            "sphinx.ext.imgmath",
            "sphinxcontrib.mermaid",
        )
    )
    assert 'autoapi_dirs = ["../src"]' in conf
    assert 'autoapi_root = "reference/api"' in conf
    assert "autoapi_keep_files = True" in conf
    assert "autoapi_add_toctree_entry = False" in conf
    assert (
        "autoapi_options = [\n"
        '    "members",\n'
        '    "undoc-members",\n'
        '    "show-inheritance",\n'
        '    "show-module-summary",\n'
        "]"
    ) in conf
    assert "autoapi_ignore" not in conf
    assert modules
    excluded_paths = _excluded_source_paths()
    assert _SOURCE_EXCLUSION_REASONS == (
        "AGENTS.md is repository guidance, not a Python module",
        "src/README.md is the source guide, not a Python module",
        "__pycache__ bytecode is generated, not source",
    )
    assert all(
        path == Path("README.md")
        or path.name == "AGENTS.md"
        or "__pycache__" in path.parts
        for path in excluded_paths
    )
    assert _toctree_entries(reference_index) == (
        *_STATIC_REFERENCE_PAGES,
        "api/index",
    )
    assert api_links == (_REFERENCE / "index.rst",)
    assert all("Goal" not in page for page in static_pages)
    assert "CLI is the supported interface" in reference_index
    assert all(page.is_file() for page in generated_pages)
    assert all(
        module in page.read_text(encoding="utf-8")
        for module, page in zip(modules, generated_pages, strict=True)
    )


def test_generated_reference_excludes_private_and_special_members(
    built_docs: Path,
) -> None:
    # Given: representative private and dunder symbols from the source tree.
    generated_reference = "\n".join(
        page.read_text(encoding="utf-8")
        for page in (built_docs / "reference/api").rglob("*.rst")
    )

    # When: generated API source is inspected after a documentation build.

    # Then: AutoAPI does not publish private or special members.
    assert "_validate_rfc3339_utc_text" not in generated_reference
    assert "__init__" not in generated_reference


def test_generated_reference_is_ignored_and_untracked() -> None:
    # Given: the generated AutoAPI index retained after a documentation build.
    generated_index = Path("docs/reference/api/index.rst")

    # When: Git evaluates its index and ignore rules.
    ignored = _git("check-ignore", generated_index.as_posix())
    tracked = _git("ls-files", "--error-unmatch", generated_index.as_posix())

    # Then: generated source remains ignored and absent from version control.
    assert ignored.returncode == 0
    assert tracked.returncode != 0


def test_reference_contract_rejects_private_member_option() -> None:
    # Given: a configuration that would expose a private member.
    conf = _read(Path("docs/conf.py")).replace(
        '"undoc-members",', '"undoc-members", "private-members",'
    )

    # When: the exact AutoAPI option set is checked.

    # Then: the Reference contract rejects that exposure.
    with pytest.raises(AssertionError):
        assert (
            "autoapi_options = [\n"
            '    "members",\n'
            '    "undoc-members",\n'
            '    "show-inheritance",\n'
            '    "show-module-summary",\n'
            "]"
        ) in conf
