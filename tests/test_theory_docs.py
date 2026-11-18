from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]
_LESSON_NAMES: Final = (
    "01-overview.py",
    "02-collect.py",
    "03-summarize.py",
    "04-compare.py",
    "05-failures-and-ci.py",
    "06-statistical-foundations.py",
    "07-summary-and-eligibility.py",
    "08-bootstrap-and-decisions.py",
    "09-plain-python-mechanics.py",
    "10-comparative-methods.py",
    "11-comparison-internal-trace.py",
)


def _read(relative_path: Path) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_furo_configuration(conf: str, pyproject: str) -> None:
    required_conf = (
        'needs_sphinx = "9.1"',
        '"autoapi.extension"',
        '"sphinx.ext.imgmath"',
        '"sphinxcontrib.mermaid"',
        'imgmath_image_format = "svg"',
        "imgmath_use_preview = True",
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
        "sphinx==9.2.0",
        "sphinx-autoapi==3.8.1",
        "sphinxcontrib-mermaid==2.1.1",
    )
    n999_paths = tuple(
        re.findall(
            r'^"([^"]+)" = \["N999"(?:, "S311")?\]$', pyproject, flags=re.MULTILINE
        )
    )
    assert n999_paths == tuple(f"examples/{name}" for name in _LESSON_NAMES)
    base_dependencies = pyproject.split("[project.scripts]", maxsplit=1)[0]
    assert all(
        dependency not in base_dependencies
        for dependency in ("furo", "marimo", "sphinx", "sphinx-autoapi")
    )


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
