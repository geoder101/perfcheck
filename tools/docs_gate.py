"""Run the authoritative Sphinx build only when documentation inputs changed.

Render inputs are hashed by ``tools.docs_inputs``. When that hash matches the
last successful build and the built HTML still exists, the gate treats the
retained documentation as up to date and skips the rebuild; pass ``--fresh`` to
force one regardless.
"""

from __future__ import annotations

import os
import subprocess
import sys
from typing import TYPE_CHECKING, Final

from tools.docs_inputs import docs_input_sha, docs_root, lock_build

if TYPE_CHECKING:
    from pathlib import Path

_ROOT = docs_root()
_STORED_KEY: Final = _ROOT / ".docs_inputs_sha"
_BUILT_INDEX = _ROOT / "docs" / "_build" / "html" / "index.html"


def _mermaid_cli_env() -> dict[str, str]:
    """Forward a provisioned Mermaid CLI entry point into the Sphinx build."""
    environment = os.environ.copy()
    cli = _ROOT / "tools/docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    if cli.is_file():
        environment["PERFCHECK_MERMAID_CLI"] = str(cli)
    return environment


def _execute_build(command: list[str], cwd: Path, env: dict[str, str]) -> int:
    """Run one uv-wrapped sphinx-build step and return its exit code."""
    return subprocess.run(  # noqa: S603 - uv is the repository's manager.
        ["uv", "run", "--group", "docs", *command],  # noqa: S607 - uv is the repository's manager.
        cwd=cwd,
        env=env,
        check=False,
    ).returncode


def is_up_to_date(key: str) -> bool:
    """Return True when the stored input hash matches and the HTML index exists."""
    stored = (
        _STORED_KEY.read_text(encoding="utf-8").strip()
        if _STORED_KEY.is_file()
        else None
    )
    return stored == key and _BUILT_INDEX.is_file()


def main() -> int:
    """Skip the rebuild when render inputs are unchanged; always fail on warnings."""
    args = sys.argv[1:]
    environment = _mermaid_cli_env()
    with lock_build():
        key = docs_input_sha()
        if "--fresh" not in args and is_up_to_date(key):
            _ = sys.stdout.write("docs up to date; skipping rebuild\n")
            return 0
        _STORED_KEY.unlink(missing_ok=True)
        clean_exit = _execute_build(
            ["sphinx-build", "-M", "clean", "docs", str(_ROOT / "docs/_build")],
            _ROOT,
            environment,
        )
        if clean_exit != 0:
            return clean_exit
        html_exit = _execute_build(
            [
                "sphinx-build",
                "-M",
                "html",
                "docs",
                str(_ROOT / "docs/_build"),
                "-E",
                "-a",
                "-W",
            ],
            _ROOT,
            environment,
        )
        if html_exit == 0:
            _ = _STORED_KEY.write_text(key, encoding="utf-8")
    return html_exit


if __name__ == "__main__":
    sys.exit(main())
