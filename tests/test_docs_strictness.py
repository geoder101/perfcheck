from pathlib import Path
from typing import Final

import pytest

from tests.docs_build import build_docs, copy_docs_project

_CONF: Final = Path(__file__).parents[1] / "docs/conf.py"


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


@pytest.mark.parametrize(
    "target", ["perfcheck.missing_reference", "pydantic.MissingReference"]
)
def test_docs_build_rejects_missing_python_references(
    target: str, tmp_path: Path
) -> None:
    # Given: fresh sources containing a broken internal or external reference.
    copy_docs_project(_CONF.parents[1], tmp_path)
    index = tmp_path / "docs/index.rst"
    with index.open("a", encoding="utf-8") as stream:
        _ = stream.write(f"\n:py:class:`{target}`\n")

    # When: the real warning-as-error build resolves Python references.
    result = build_docs(tmp_path)

    # Then: unresolved names fail the build instead of being silently hidden.
    assert result.returncode != 0
    assert f"reference target not found: {target}" in result.stderr
