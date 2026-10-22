import re
from pathlib import Path

import pytest

_README_PATH = Path(__file__).parents[1] / "README.md"


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
        "perfcheck collect --help",
        "perfcheck summarize --help",
        "perfcheck compare --help",
        "uv sync --group dev",
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

    # Then: users reach the project landing page before the ten-lesson curriculum.
    assert targets == ("docs/index.rst", "examples/README.md")
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


def test_governance_maps_optional_documentation_without_a_public_python_api(
    built_docs: Path,
) -> None:
    # Given: contributor guidance alongside the current build recipes.
    root = _README_PATH.parent
    guidance = (root / "AGENTS.md").read_text(encoding="utf-8")

    # When: contributors follow its documentation source map.
    paths = tuple(
        match.group(1)
        for match in re.finditer(r"`(docs/[^`]+|examples/README.md)`", guidance)
    )

    # Then: all four Diataxis paths exist and generated API pages stay internal.
    assert paths
    assert all((built_docs.parent / path).exists() for path in paths)
    assert all(
        f"docs/{section}/" in paths
        for section in ("tutorials", "how-to", "reference", "explanation")
    )
    assert "source-parsed" in guidance
    assert "does not import" in guidance
    assert "just docs-preview [port]" in guidance
    assert "CLI only" in guidance
