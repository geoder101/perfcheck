from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.docs_build import ensure_built_docs

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture(scope="session")
def built_docs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("docs-project")
    result = ensure_built_docs(project)
    if result is not None:
        assert result.returncode == 0, result.stdout + result.stderr
        assert "WARNING" not in result.stderr, result.stderr
    return project / "docs"
