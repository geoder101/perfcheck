import os
import re
import subprocess
from pathlib import Path
from shutil import copytree, ignore_patterns


def copy_docs_project(source: Path, destination: Path) -> None:
    for directory in ("docs", "src", "examples", "tests", "tools"):
        _ = copytree(
            source / directory,
            destination / directory,
            ignore=ignore_patterns(
                "_build", "api", "__pycache__", "node_modules", ".cache"
            ),
        )


def build_docs(project: Path) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).parents[1]
    environment = os.environ.copy()
    cli = root / "tools/docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    if cli.is_file():
        _ = environment.setdefault("PERFCHECK_MERMAID_CLI", str(cli))
    return subprocess.run(  # noqa: S603 - fixed documentation build command.
        [  # noqa: S607 - uv is the repository's required environment manager.
            "uv",
            "run",
            "--group",
            "docs",
            "sphinx-build",
            "-b",
            "html",
            str(project / "docs"),
            str(project / "docs/_build/html"),
            "-E",
            "-a",
            "-W",
        ],
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )


def assert_local_svg_urls(source: str) -> None:
    for match in re.finditer(r"url\s*\(([^)]*)\)", source, re.IGNORECASE):
        assert re.fullmatch(r"""(['"]?)#[^\s'"()]+\1""", match.group(1).strip())
