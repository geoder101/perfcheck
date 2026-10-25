"""Run the fixed full-suite coverage gate with fresh repository-owned reports."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main() -> int:
    """Reject overrides, remove old evidence safely, and preserve Just's status."""
    if len(sys.argv) != 1:
        _ = sys.stderr.write("coverage-check accepts no arguments\n")
        return 2
    root = Path(__file__).resolve().parents[1]
    output = root / "coverage"
    try:
        # Preflight every owned path before deleting anything or invoking pytest.
        if output.is_symlink() or output.is_junction():
            _ = sys.stderr.write(
                f"refusing symlink/junction coverage output: {output}\n"
            )
            return 2
        for path in output.rglob("*"):
            if path.is_symlink() or path.is_junction():
                _ = sys.stderr.write(
                    f"refusing symlink/junction coverage output: {path}\n"
                )
                return 2
        owned = (output / "html", output / "coverage.json", *output.glob(".coverage*"))
        for path in owned:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)
    except OSError as error:
        _ = sys.stderr.write(f"cannot clean coverage outputs: {error}\n")
        return 2
    just = shutil.which("just")
    if just is None:
        _ = sys.stderr.write("coverage-check requires just on PATH\n")
        return 2
    return subprocess.run(  # noqa: S603
        (just, "coverage", "--cov-fail-under=99"),
        cwd=root,
        env={
            key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"
        },
        check=False,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
