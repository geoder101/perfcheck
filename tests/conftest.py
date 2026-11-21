from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.docs_build import ensure_built_docs

if TYPE_CHECKING:
    from pathlib import Path


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Budget native render fixtures for their 600-second child plus lock wait."""
    for item in items:
        if isinstance(item, pytest.Function) and "built_docs" in item.fixturenames:
            item.add_marker(pytest.mark.timeout(900))


@pytest.fixture(scope="session")
def built_docs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("docs-project")
    result = ensure_built_docs(project)
    if result is not None:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WARNING" not in result.stderr, result.stderr
    return project / "docs"
