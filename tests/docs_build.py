import subprocess
from pathlib import Path
from shutil import copytree, ignore_patterns


def copy_docs_project(source: Path, destination: Path) -> None:
    for directory in ("docs", "src", "examples", "tests"):
        _ = copytree(
            source / directory,
            destination / directory,
            ignore=ignore_patterns("_build", "api", "__pycache__"),
        )


def build_docs(project: Path) -> subprocess.CompletedProcess[str]:
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
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
