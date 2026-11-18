import re
from pathlib import Path

import pytest

_README_PATH = Path(__file__).parents[1] / "README.md"


def test_docs_tools_provisions_only_when_explicitly_requested() -> None:
    # Given: the canonical contributor command manifest.
    source = (_README_PATH.parent / "justfile").read_text(encoding="utf-8")
    # When: the explicit provisioning recipe is inspected.
    recipe = source.split("\ndocs-tools:\n", 1)[1].split("\n\n", 1)[0]
    # Then: locked dependencies precede a deliberate browser installation.
    cli = "tools/docs/node_modules/puppeteer/lib/puppeteer/node/cli.js"
    assert recipe.splitlines() == [
        "  npm ci --prefix tools/docs --ignore-scripts",
        f"  node {cli} browsers install chrome",
    ]
    assert "docs-tools" not in source.split("\ncheck:", 1)[1].splitlines()[0]


def test_docs_check_delegates_to_cache_aware_gate() -> None:
    # Given: a renderer configuration can change without changing diagram source.
    source = (_README_PATH.parent / "justfile").read_text(encoding="utf-8")
    # When: the documentation recipe is inspected.
    block = source.split("\ndocs-check *args:\n", 1)[1].split("\n\n", 1)[0]
    recipe = block.splitlines()
    # Then: the cache-aware gate decides when to build and --fresh forces a rebuild.
    assert recipe == ["  uv run python -m tools.docs_gate {{args}}"]
    assert "Pass --fresh to force a rebuild" in source


@pytest.mark.parametrize("command", ["sync", "coverage", "coverage-check", "mutation"])
def test_developer_guides_map_existing_opt_in_recipes(command: str) -> None:
    # Given: the actual canonical recipes and both developer entry points.
    root = _README_PATH.parent
    recipes = (root / "justfile").read_text(encoding="utf-8")
    guides = (_README_PATH, root / "AGENTS.md")

    # When: a contributor looks up each quality command.
    documented = tuple(path.read_text(encoding="utf-8") for path in guides)

    # Then: both guides name a real recipe rather than an invented command.
    assert re.search(rf"^{re.escape(command)}(?:[ *:].*)?:", recipes, re.MULTILINE)
    assert all(f"just {command}" in source for source in documented)
