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


def test_readme_does_not_claim_commands_are_future_work() -> None:
    # Given: the project README distributed with the package.
    readme = " ".join(_README_PATH.read_text(encoding="utf-8").lower().split())

    # When: users read the current command contract.

    # Then: it does not describe implemented commands as future work.
    assert "commands will be added" not in readme


def test_readme_documents_supported_workflow_and_scope() -> None:
    # Given: the project README distributed with the package.
    readme = _README_PATH.read_text(encoding="utf-8")

    # When: users look up the supported workflow and its boundaries.

    # Then: the README lists only current commands, quality checks, and scope.
    required_claims = (
        "just cli --help",
        "just cli collect --help",
        "just cli summarize --help",
        "just cli compare --help",
        "just sync",
        "just check",
        "Internal implementation may change or be removed",
    )
    assert all(claim in readme for claim in required_claims)


def _assert_local_links(source: str, directory: Path) -> tuple[str, ...]:
    targets = tuple(
        match.group(1) for match in re.finditer(r"\[[^\]]+\]\(([^)]+)\)", source)
    )
    local_targets = tuple(target for target in targets if "://" not in target)
    assert local_targets
    assert all((directory / target).is_file() for target in local_targets)
    return local_targets


@pytest.mark.parametrize("relative_path", ["README.md", "examples/README.md"])
def test_all_markdown_entrypoint_links_resolve(relative_path: str) -> None:
    # Given: a public Markdown entry point with local lesson and explanation links.
    path = _README_PATH.parent / relative_path

    # When: all local destinations are resolved in that document's context.
    targets = _assert_local_links(path.read_text(encoding="utf-8"), path.parent)

    # Then: every linked file exists, including the two complementary lessons.
    assert targets


def test_readme_links_project_first_docs_and_curriculum() -> None:
    # Given: the short project entry point, not a duplicate documentation manual.
    source = _README_PATH.read_text(encoding="utf-8")

    # When: its Markdown destinations are resolved from the repository root.
    targets = _assert_local_links(source, _README_PATH.parent)

    # Then: the project landing and docs pages publish to Pages, while the local
    # curriculum index link stays local alongside them.
    assert targets == ("examples/README.md",)
    for published_page in (
        "https://geoder101.github.io/perfcheck/index.html",
        "https://geoder101.github.io/perfcheck/explanation/learning-paths.html",
        "https://geoder101.github.io/perfcheck/tutorials/performance-verification-case-study.html",
        "https://geoder101.github.io/perfcheck/how-to/prometheus-authentication.html",
    ):
        assert published_page in source
    assert "just docs-check" in source
    assert "just docs-preview" in source
    assert "optional" in source.lower()


def test_readme_link_contract_rejects_a_missing_target(tmp_path: Path) -> None:
    # Given: a README destination missing from a temporary checkout.
    source = "[Project documentation](docs/index.rst)"

    # When: the same link contract resolves that checkout.
    # Then: a plausible label cannot mask a missing documentation target.
    with pytest.raises(AssertionError):
        _ = _assert_local_links(source, tmp_path)


def test_governance_maps_optional_documentation_without_a_public_python_api() -> None:
    # Given: contributor guidance alongside the current build recipes.
    root = _README_PATH.parent
    guidance = (root / "AGENTS.md").read_text(encoding="utf-8")
    docs_guide = (root / "docs/README.md").read_text(encoding="utf-8")

    # When: contributors follow its documentation source map.
    paths = tuple(
        match.group(1)
        for match in re.finditer(r"\[[^\]]+\]\(([^)]+/README\.md)\)", guidance)
    )

    # Then: root guidance delegates to real guides; Docs owns the site map.
    assert {"docs/README.md", "examples/README.md"} <= set(paths)
    assert all((root / path).is_file() for path in paths)
    for section in ("tutorials", "how-to", "reference", "explanation"):
        assert (
            f"https://geoder101.github.io/perfcheck/{section}/index.html" in docs_guide
        )
        assert (root / "docs" / section / "index.rst").is_file()
    assert "source-parsed AutoAPI" in docs_guide
    assert "without importing application modules" in docs_guide
    assert "Reference index owns its site navigation" in docs_guide
    assert "not a supported public Python API" in docs_guide
    assert "CLI-only" in guidance
    assert "just docs-preview [port]" in guidance
    assert "before serving `docs/_build/html` (default 8000)" in guidance
    assert "optional docs dependency group" in docs_guide


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


def test_readme_distinguishes_exploration_from_fresh_coverage_gate() -> None:
    # Given: coverage is opt-in and application measurement has a fixed scope.
    root = _README_PATH.parent
    recipe = (root / "tools/coverage_gate.py").read_text(encoding="utf-8")

    # When: users read the measurement and downloadable evidence contract.
    source = " ".join(_README_PATH.read_text(encoding="utf-8").split())

    # Then: the fixed gate, raw data, provenance and failure limits are explicit.
    assert '"--cov-fail-under=99"' in recipe
    assert all(
        claim in source
        for claim in (
            "exploratory",
            "no threshold",
            "99%",
            "statements and branches",
            "coverage.py precision",
            "coverage/.coverage",
            "tested SHA",
            "PR head",
            "partial",
            "unavailable",
            "seven days",
        )
    )
    assert "There is no coverage threshold." not in source


def test_readme_explains_optional_mutation_and_safe_fresh_runs() -> None:
    # Given: the pilot is deliberately bounded and refuses existing output.
    root = _README_PATH.parent
    config = (root / "pyproject.toml").read_text(encoding="utf-8")

    # When: developers read how to run and interpret the pilot.
    source = " ".join(_README_PATH.read_text(encoding="utf-8").split())

    # Then: instructions match the target, selection, cost and evidence contract.
    for path in (
        "src/perfcheck/regression_aggregation.py",
        "tests/test_suite_aggregation.py",
    ):
        assert path in source
        assert path in config
    assert all(
        claim in source
        for claim in (
            "Unix-only",
            "one worker",
            "600-second",
            "nonempty",
            "archive",
            "just sync",
            "JSON",
            "results.txt",
            "status.json",
            "advisory",
            "no score gate",
            "not native mutmut HTML",
        )
    )


def test_readme_records_hosted_pages_site_and_owner_setup() -> None:
    # Given: the GitHub repository and its Pages docs site are published.
    root = _README_PATH.parent
    workflow = (root / ".github/workflows/pages.yml").read_text(encoding="utf-8")

    # When: the owner follows the one-time hosting checklist.
    source = " ".join(_README_PATH.read_text(encoding="utf-8").split())

    # Then: the hosted Pages URL is live and the owner-hosted checklist is documented.
    assert "github.event.repository.default_branch" in workflow
    assert all(
        claim in source
        for claim in (
            "Settings > Pages",
            "GitHub Actions",
            "github-pages",
            "default branch",
            "no tags",
            "reviewers",
            "pinned actions",
            "Linux/macOS/Windows",
            "PRs",
            "non-default",
            "internal Python",
            "geoder101.github.io/perfcheck",
        )
    )
