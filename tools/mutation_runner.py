"""Run the opt-in aggregation experiment without touching working source."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import time
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from tools.mutation_campaign import BUDGET, SELECTION, TARGET, execute
from tools.mutation_evidence import EvidenceError, completion, require


def snapshot(root: Path, destination: Path) -> None:
    """Copy only experiment inputs, excluding caches and generated outputs."""
    for directory in ("src", "tests", "tools"):
        _ = shutil.copytree(
            root / directory,
            destination / directory,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                ".pytest_cache",
                ".venv",
                "build",
                "dist",
                "coverage",
                "mutation",
                "mutants",
            ),
        )
    for name in ("pyproject.toml", "uv.lock", "README.md"):
        _ = shutil.copy2(root / name, destination / name)


def source_identity(root: Path) -> tuple[tuple[str, str], ...]:
    """Hash the complete source package before and after the isolated run."""

    def scan_error(error: OSError) -> None:
        raise error

    files = sorted(
        directory / name
        for directory, _, names in (root / "src").walk(on_error=scan_error)
        for name in names
        if name.endswith(".py")
    )
    return tuple(
        (str(path.relative_to(root)), hashlib.sha256(path.read_bytes()).hexdigest())
        for path in files
    )


def prepare_output(output: Path) -> bool:
    """Reject unsupported platforms and stale or redirected evidence outputs."""
    if sys.platform == "win32":
        _ = sys.stderr.write(
            "Mutation needs Unix fork; run just mutation on Linux/macOS.\n"
        )
        return False
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        _ = sys.stderr.write("Archive or remove mutation/ before a fresh experiment.\n")
        return False
    output.mkdir(parents=True, exist_ok=True)
    return True


def write_manifest(root: Path, output: Path) -> tuple[tuple[str, str], ...]:
    """Record exact source and locked environment identity before execution."""
    identity = source_identity(root)
    manifest = {
        "target": TARGET,
        "tests": SELECTION,
        "source_sha256": hashlib.sha256((root / TARGET).read_bytes()).hexdigest(),
        "source_package_sha256": identity,
        "lock_sha256": hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest(),
        "python": sys.version,
        "executable": sys.executable,
        "versions": {name: version(name) for name in ("mutmut", "libcst", "pytest")},
        "child_budget_seconds": BUDGET,
        "workers": 1,
    }
    _ = (output / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return identity


def run_pilot(root: Path, output: Path) -> int:
    """Persist an honest status for initialization, campaign and inspection failures."""
    if not prepare_output(output):
        return 2
    started = time.monotonic()
    status = "invalid"
    detail = "experiment did not complete"
    source_unchanged = False
    try:
        source_before = write_manifest(root, output)
        with tempfile.TemporaryDirectory(prefix="perfcheck-mutation-") as temporary:
            work = Path(temporary)
            snapshot(root, work)
            require(
                source_identity(work) == source_before,
                "snapshot source identity mismatch",
            )
            result = execute(work, output)
        source_unchanged = source_identity(root) == source_before
        require(source_unchanged, "working source changed during experiment")
        status = completion(result.returncode, timed_out=result.timed_out)
        detail = (
            "600-second child wall budget exhausted; process group killed"
            if result.timed_out
            else "validated inventory, baseline, forced failure and imports"
        )
    except InterruptedError, KeyboardInterrupt:
        status = "incomplete"
        detail = "runner interrupted; active child process group killed"
    except (EvidenceError, OSError, ValueError, PackageNotFoundError) as error:
        detail = str(error)
    _ = (output / "status.json").write_text(
        json.dumps(
            {
                "status": status,
                "detail": detail,
                "elapsed_seconds": time.monotonic() - started,
                "source_unchanged": source_unchanged,
            },
            indent=2,
        )
    )
    _ = sys.stdout.write(f"Mutation {status}: {detail}. Evidence: {output}\n")
    return 0 if status == "complete" else 1


def main() -> int:
    """Use the existing locked interpreter, never resolve a snapshot environment."""
    root = Path(__file__).resolve().parents[1]
    return run_pilot(root, root / "mutation")


if __name__ == "__main__":
    raise SystemExit(main())
