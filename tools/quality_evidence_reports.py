"""Fresh, readable coverage report validation and allowlisted artifact staging."""

from __future__ import annotations

import math
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

from coverage import Coverage, CoverageData

from tools.quality_evidence_html import validate_html
from tools.quality_evidence_models import (
    CoverageReport,
    EvidenceError,
    RunStart,
    Totals,
    require,
)


def safe_tree(path: Path) -> None:
    """Reject redirected paths and propagate scan errors before copying/deleting."""
    require(not (path.is_symlink() or path.is_junction()))
    if path.is_dir():
        for directory, directories, files in path.walk(on_error=_scan_error):
            for name in (*directories, *files):
                child = directory / name
                require(not (child.is_symlink() or child.is_junction()))


def _scan_error(error: OSError) -> None:
    raise EvidenceError from error


def clear_staged_reports(destination: Path) -> None:
    """Discard only staged measurement outputs before export or after copy failure."""
    safe_tree(destination)
    for name in ("html", "coverage.json", ".coverage", "provenance.json"):
        path = destination / name
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink(missing_ok=True)


def stage_reports(root: Path, start: RunStart, finished_ns: int) -> Totals:
    """Publish only a complete current-invocation report set, never stale inputs."""
    output = root / "coverage"
    safe_tree(output / "html")
    paths = (output / ".coverage", output / "coverage.json", output / "html/index.html")
    for path in paths:
        safe_tree(path)
        require(path.is_file())
        require(start.started_ns <= path.stat().st_mtime_ns <= finished_ns)
    report = CoverageReport.model_validate_json(paths[1].read_bytes())
    totals = report.totals
    require(bool(report.files))
    require(totals.num_statements + totals.num_branches > 0)
    require(totals.covered_lines + totals.missing_lines == totals.num_statements)
    require(totals.covered_branches + totals.missing_branches == totals.num_branches)
    require(math.isclose(totals.percent_covered, totals.combined_percent))
    file_counts = tuple(
        sum(values)
        for values in zip(
            *(file.summary.counts for file in report.files.values()), strict=True
        )
    )
    require(file_counts == totals.counts)
    require(paths[0].read_bytes().startswith(b"SQLite format 3\x00"))
    data = CoverageData(basename=str(paths[0]))
    data.read()
    require(data.has_arcs() and bool(data.measured_files()))
    reported_files = {str((root / name).resolve()) for name in report.files}
    require(data.measured_files() == reported_files)
    with TemporaryDirectory(prefix="perfcheck-report-validation-") as temporary:
        regenerated = Path(temporary) / "coverage.json"
        raw_copy = Path(temporary) / ".coverage"
        _ = shutil.copyfile(paths[0], raw_copy)
        measurement = Coverage(
            data_file=str(raw_copy), config_file=str(root / "pyproject.toml")
        )
        measurement.load()
        _ = measurement.json_report(
            morfs=sorted(reported_files), outfile=str(regenerated)
        )
        authoritative = CoverageReport.model_validate_json(regenerated.read_bytes())
    require(authoritative.totals.counts == totals.counts)
    require(
        {name: file.summary.counts for name, file in authoritative.files.items()}
        == {name: file.summary.counts for name, file in report.files.items()}
    )
    validate_html(output / "html", start.started_ns, finished_ns)
    destination = output / "evidence"
    _ = shutil.copyfile(paths[0], destination / ".coverage")
    _ = shutil.copyfile(paths[1], destination / "coverage.json")
    _ = shutil.copytree(
        output / "html", destination / "html", ignore=shutil.ignore_patterns(".*")
    )
    return totals
