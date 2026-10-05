from pathlib import Path

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
        "uv run pytest",
        "uv run ruff check .",
        "uv run basedpyright",
        "Internal implementation may change or be removed",
    )
    assert all(claim in readme for claim in required_claims)
