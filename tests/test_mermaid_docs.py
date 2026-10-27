from pathlib import Path
from typing import Final

import pytest

from tests.docs_build import assert_local_svg_urls, copy_docs_project

_ROOT: Final = Path(__file__).parents[1]


def test_mermaid_is_authored_and_rendered_at_build_time() -> None:
    # Given: the authored landing page and shared Sphinx renderer configuration.
    source = (_ROOT / "docs/index.rst").read_text(encoding="utf-8")
    conf = (_ROOT / "docs/conf.py").read_text(encoding="utf-8")
    # When: the diagram's authoring and rendering boundaries are inspected.
    # Then: authors use a real directive and all diagrams share local SVG defaults.
    assert ".. container:: workflow-diagram" in source
    assert "   .. mermaid::" in source
    assert "flowchart TD" in source
    assert "accTitle:" in source
    assert "accDescr:" in source
    assert "_static/workflow.svg" not in source
    assert not (_ROOT / "docs/_static/workflow.svg").exists()
    assert (
        'mermaid_cmd = [sys.executable, str(_PROJECT_ROOT / "tools/mermaid.py")]'
        in conf
    )
    assert "mermaid_cmd_shell = False" in conf
    assert 'mermaid_output_format = "svg"' in conf
    assert 'mermaid_params = ["--no-font-embed"]' in conf
    assert "mermaid_d3_zoom = False" in conf
    assert "mermaid_fullscreen = False" in conf
    assert '"htmlLabels": False' in conf
    assert '"flowchart": {"htmlLabels": False' in conf
    assert '"fontSize": "16px"' in conf
    assert "system-ui" in conf


def test_docs_copy_keeps_renderer_inputs_without_install_state(tmp_path: Path) -> None:
    # Given: a project with a launcher, browser profile and heavy local install state.
    source = tmp_path / "source"
    for directory in ("docs", "src", "examples", "tests", "tools"):
        (source / directory).mkdir(parents=True)
    for relative in (
        "tools/mermaid.py",
        "tools/docs/puppeteer-native.json",
        "tools/docs/node_modules/ignored.js",
        "tools/docs/.cache/ignored",
    ):
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text("fixture", encoding="utf-8")
    destination = tmp_path / "copy"
    # When: an isolated documentation build copies its inputs.
    copy_docs_project(source, destination)
    # Then: launch/config inputs survive without duplicating dependencies or caches.
    assert (destination / "tools/mermaid.py").is_file()
    assert (destination / "tools/docs/puppeteer-native.json").is_file()
    assert not (destination / "tools/docs/node_modules").exists()
    assert not (destination / "tools/docs/.cache").exists()


@pytest.mark.parametrize("target", ["#arrow", "'#arrow'", '"#arrow"', " '#arrow' "])
def test_svg_url_contract_accepts_local_markers(target: str) -> None:
    # Given: Mermaid may serialize local markers with optional matching quotes.
    source = f"marker-end: url({target})"
    # When/Then: valid local fragment syntax remains an accepted SVG resource.
    assert_local_svg_urls(source)


@pytest.mark.parametrize(
    "target",
    [
        "https://example.com/a",
        "//example.com/a",
        "data:image/svg+xml,a",
        "arrow.svg#id",
        "'#arrow\"",
        "'#arrow",
        "#arrow'",
    ],
)
def test_svg_url_contract_rejects_external_or_malformed_urls(target: str) -> None:
    # Given: a nonlocal resource or invalid quote syntax in SVG CSS.
    source = f"marker-end: url({target})"
    # When/Then: external and malformed destinations cannot masquerade as fragments.
    with pytest.raises(AssertionError):
        assert_local_svg_urls(source)
