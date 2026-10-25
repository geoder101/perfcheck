"""Stage approved mutation diagnostics without uploading redirected evidence."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Final

from tools.mutation_campaign import TARGET
from tools.mutation_evidence import EvidenceError, require

_FILES: Final = (
    "status.json",
    "manifest.json",
    "outcomes.json",
    "inspection.json",
    "imports.jsonl",
    "inspection-imports.jsonl",
    "results.txt",
    "parse.log",
    "baseline.log",
    "run.log",
    "export.log",
    "generated-baseline.log",
    "forced-failure.log",
    "inspect-killed.diff",
    "inspect-survived.diff",
    *(
        f"inspect-{verdict}-{index}.log"
        for verdict in ("killed", "survived")
        for index in range(3)
    ),
    "mutants/mutmut-cicd-stats.json",
    "mutants/mutmut-stats.json",
    f"mutants/{TARGET}",
    f"mutants/{TARGET}.meta",
    f"mutants/{TARGET}.spans",
)


def safe(root: Path, relative: str) -> Path:
    """Reject redirected candidates and ancestors within their trusted base."""
    path = root / relative
    require(
        all(
            not part.is_symlink()
            for part in (path, *path.parents)
            if part.is_relative_to(root)
        ),
        "redirected evidence path",
    )
    return path


def ci_directory() -> Path:
    """Keep generated CI receipts out of the checkout and product artifacts."""
    return safe(Path(os.environ["RUNNER_TEMP"]).resolve(), "mutation-ci")


def stage(root: Path, ci: Path) -> bool:
    """Retain independently safe diagnostics while rejecting any unsafe candidate."""
    destination = safe(ci, "evidence")
    destination.mkdir()
    accepted = True
    candidates = (
        (ci, "start.json"),
        (ci, "stdout.log"),
        *((root, f"mutation/{name}") for name in _FILES),
    )
    for base, name in candidates:
        try:
            source = safe(base, name)
        except EvidenceError:
            accepted = False
            continue
        if source.is_file():
            relative = Path("mutation-ci") / name if base == ci else Path(name)
            output = destination / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            _ = shutil.copyfile(source, output)
    return accepted
