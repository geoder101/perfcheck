from pathlib import Path
from typing import Final

import pytest

from tests.docs_build import build_docs, copy_docs_project

_CONF: Final = Path(__file__).parents[1] / "docs/conf.py"


def _mermaid_project(project: Path) -> None:
    copy_docs_project(_CONF.parents[1], project)
    _ = (project / "docs/index.rst").write_text(
        """Renderer contract
=================

.. mermaid::

   flowchart TD
   A --> B
""",
        encoding="utf-8",
    )
    with (project / "docs/conf.py").open("a", encoding="utf-8") as stream:
        _ = stream.write(
            """
extensions = ["sphinxcontrib.mermaid"]
exclude_patterns = ["_build", "_templates", "tutorials",
                    "how-to", "reference", "explanation"]
"""
        )


def _assert_strict_reference_policy(conf: str) -> None:
    assert "nitpicky = True" in conf
    assert "nitpicky = False" not in conf
    assert "nitpick_ignore_regex" not in conf
    assert "nitpick_ignore" not in conf
    assert "suppress_warnings" not in conf


def test_documentation_keeps_python_reference_warnings_enabled() -> None:
    # Given: the configuration used for every documentation build.
    conf = _CONF.read_text(encoding="utf-8")

    # When: the strict reference policy is inspected.
    # Then: no reference category is hidden by a blanket suppression.
    _assert_strict_reference_policy(conf)


@pytest.mark.parametrize(
    "suppression",
    [
        'nitpick_ignore_regex = [(r"py:.*", r".*")]',
        'suppress_warnings = ["ref.*"]',
        "nitpicky = False",
    ],
)
def test_reference_policy_rejects_blanket_suppression(suppression: str) -> None:
    # Given: a proposed configuration that silences Python reference warnings.
    conf = _CONF.read_text(encoding="utf-8")
    mutated = conf + "\n" + suppression

    # When: the same policy contract checks the proposed configuration.
    # Then: blanket ignores and disabled strictness are rejected.
    with pytest.raises(AssertionError):
        _assert_strict_reference_policy(mutated)


_MISSING_INTERNAL_REFERENCE: Final = "perfcheck.missing_reference"
_MISSING_EXTERNAL_REFERENCE: Final = "pydantic.MissingReference"
_MISSING_PYTHON_REFERENCES: Final = (
    _MISSING_INTERNAL_REFERENCE,
    _MISSING_EXTERNAL_REFERENCE,
)


def test_docs_build_rejects_missing_python_references(tmp_path: Path) -> None:
    # Given: fresh sources containing a broken internal and external reference.
    copy_docs_project(_CONF.parents[1], tmp_path)
    index = tmp_path / "docs/index.rst"
    with index.open("a", encoding="utf-8") as stream:
        for target in _MISSING_PYTHON_REFERENCES:
            _ = stream.write(f"\n:py:class:`{target}`\n")
    # Scope the tree down so only the affected page renders; reference
    # resolution is unchanged, which keeps the strict build fast.
    with (tmp_path / "docs/conf.py").open("a", encoding="utf-8") as stream:
        _ = stream.write(
            """
exclude_patterns = ["_build", "_templates", "tutorials",
                    "how-to", "reference", "explanation"]
"""
        )

    # When: the real warning-as-error build resolves Python references.
    result = build_docs(tmp_path)

    # Then: unresolved names fail the build instead of being silently hidden.
    assert result.returncode != 0
    for target in _MISSING_PYTHON_REFERENCES:
        assert f"reference target not found: {target}" in result.stderr


@pytest.mark.parametrize("failure", ["missing", "nonzero", "no-output"])
def test_docs_build_rejects_renderer_failure(failure: str, tmp_path: Path) -> None:
    # Given: a fresh build with an unavailable or broken build-time renderer.
    _mermaid_project(tmp_path)
    command = [str(tmp_path / "missing-renderer")]
    if failure != "missing":
        command = [
            "sys.executable",
            "-c",
            "import sys; sys.exit(23)" if failure == "nonzero" else "pass",
        ]
    expression = repr(command).replace("'sys.executable'", "sys.executable")
    with (tmp_path / "docs/conf.py").open("a", encoding="utf-8") as stream:
        _ = stream.write(f"\nimport sys\nmermaid_cmd = {expression}\n")
    # When: Sphinx attempts the real build under warnings-as-errors.
    result = build_docs(tmp_path)
    # Then: failed rendering is never accepted as a successful raw/JS fallback.
    assert result.returncode != 0
    assert "mermaid" in result.stderr.lower()
    html = tmp_path / "docs/_build/html/index.html"
    if html.exists():
        assert 'class="mermaid"' not in html.read_text(encoding="utf-8")


def test_docs_build_rejects_invalid_mermaid(tmp_path: Path) -> None:
    # Given: an authored Mermaid syntax error alongside the valid workflow.
    _mermaid_project(tmp_path)
    with (tmp_path / "docs/index.rst").open("a", encoding="utf-8") as stream:
        _ = stream.write("\n.. mermaid::\n\n   flowchart TD\n   A[unterminated\n")
    # When: the actual Mermaid CLI parses the invalid diagram during a strict build.
    result = build_docs(tmp_path)
    # Then: invalid authored content is a build failure, not deferred client work.
    assert result.returncode != 0
    assert "mermaid exited with error" in result.stderr.lower()
    assert "parse error" in result.stderr.lower()


def test_docs_build_accepts_supported_mermaid_config_types(tmp_path: Path) -> None:
    # Given: a real build using list argv and a boolean shell=False configuration.
    _mermaid_project(tmp_path)
    # When: Sphinx checks configuration types and renders a local SVG.
    result = build_docs(tmp_path)
    # Then: supported types do not require silencing warnings to pass the build.
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING" not in result.stderr
