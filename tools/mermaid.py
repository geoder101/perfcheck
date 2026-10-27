"""Run explicitly provisioned Mermaid tooling without a shell or installation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, override

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True, slots=True)
class LauncherError(Exception):
    """Describe an invalid launcher configuration before spawning a child."""

    reason: str

    @override
    def __str__(self) -> str:
        return self.reason


def command(args: Sequence[str], root: Path) -> list[str]:
    """Resolve one renderer and append the explicit browser launch profile."""
    container = os.environ.get("PERFCHECK_DOCS_CONTAINER") == "1"
    opt_in = os.environ.get("PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX")
    if opt_in is not None and (not container or opt_in != "1"):
        reason = (
            "PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX must be 1 and requires "
            "PERFCHECK_DOCS_CONTAINER=1"
        )
        raise LauncherError(reason)
    profile = "puppeteer.json"
    if container:
        profile = (
            "puppeteer-container-nosandbox.json"
            if opt_in == "1"
            else "puppeteer-container.json"
        )
    override_cli = os.environ.get("PERFCHECK_MERMAID_CLI")
    local = root / "tools/docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    if override_cli is not None:
        local = Path(override_cli)
        if not local.is_absolute() or not local.is_file():
            reason = "PERFCHECK_MERMAID_CLI must name an existing absolute JS file"
            raise LauncherError(reason)
    if local.is_file():
        node = shutil.which("node")
        if not node or Path(node).suffix.lower() in {".cmd", ".bat"}:
            reason = "A real Node executable is required for the selected JS CLI"
            raise LauncherError(reason)
        executable = [node, str(local)]
    else:
        global_cli = shutil.which("mmdc") if sys.platform != "win32" else None
        if not global_cli:
            reason = (
                "Mermaid CLI unavailable: provision tools/docs with npm ci "
                "--ignore-scripts and explicitly install Puppeteer's Chrome, "
                "or set PERFCHECK_MERMAID_CLI"
            )
            raise LauncherError(reason)
        executable = [global_cli]
    return [
        *executable,
        *args,
        "--puppeteerConfigFile",
        str(root / "tools/docs" / profile),
    ]


def main() -> int:
    """Preserve inherited streams and the selected child's exit status."""
    try:
        argv = command(sys.argv[1:], Path(__file__).resolve().parents[1])
        return subprocess.run(argv, shell=False, check=False).returncode  # noqa: S603
    except (LauncherError, OSError) as error:
        _ = sys.stderr.write(f"Mermaid launcher: {error}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
