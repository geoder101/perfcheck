from pathlib import Path

import pytest

from tests.docs_build import build_docs, copy_docs_project


@pytest.fixture(scope="session")
def built_docs(tmp_path_factory: pytest.TempPathFactory) -> Path:
    project = tmp_path_factory.mktemp("docs-project")
    copy_docs_project(Path(__file__).parents[1], project)
    result = build_docs(project)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "WARNING" not in result.stderr, result.stderr
    return project / "docs"
