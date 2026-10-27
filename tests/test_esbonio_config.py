import subprocess
import sys
from pathlib import Path

import pytest

from tests.docs_build import copy_docs_project


@pytest.mark.parametrize("generate", [False, True])
def test_sphinx_setup_respects_autoapi_generation(
    tmp_path: Path, generate: bool
) -> None:
    # Given: isolated documentation sources without generated API pages.
    copy_docs_project(Path(__file__).parents[1], tmp_path)

    # When: Sphinx initializes with the editor or canonical generation setting.
    result = subprocess.run(  # noqa: S603 - fixed Sphinx initialization script.
        [
            sys.executable,
            "-c",
            """from sphinx.application import Sphinx
import sys
Sphinx(sys.argv[1], sys.argv[1], sys.argv[2], sys.argv[3],
       buildername='dummy',
       confoverrides={'autoapi_generate_api_docs': sys.argv[4] == 'True'})
""",
            str(tmp_path / "docs"),
            str(tmp_path / "output"),
            str(tmp_path / "doctrees"),
            str(generate),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )

    # Then: only canonical startup creates the API index.
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "docs/reference/api/index.rst").exists() == generate
