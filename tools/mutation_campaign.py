"""Execute and retain one isolated, bounded mutation campaign."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Final

from tools.mutation_evidence import check_phase, verify_experiment
from tools.mutation_inspection import inspect_mutants
from tools.mutation_process import Command, run_child

if TYPE_CHECKING:
    from tools.mutation_process import ChildResult

TARGET: Final = "src/perfcheck/regression_aggregation.py"
SELECTION: Final = "tests/test_suite_aggregation.py"
BUDGET: Final = 600


def execute(work: Path, output: Path) -> ChildResult:
    """Keep native evidence even when export or inspection fails."""
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "PYTHONPATH",
            "PYTEST_ADDOPTS",
            "PYTEST_PLUGINS",
            "MUTANT_UNDER_TEST",
            "COVERAGE_PROCESS_START",
        }
    }
    env["PYTHONPATH"] = os.pathsep.join((str(work / "src"), str(work)))
    parse_script = f"""import libcst
from pathlib import Path
libcst.parse_module(Path({TARGET!r}).read_text())
"""
    parse = run_child(
        Command((sys.executable, "-c", parse_script), work, env),
        output / "parse.log",
        30,
    )
    check_phase(parse, "LibCST parse")
    baseline = run_child(
        Command(
            (sys.executable, "-m", "pytest", "-p", "no:pytest_cov", SELECTION),
            work,
            env,
        ),
        output / "baseline.log",
        60,
    )
    check_phase(baseline, "clean selected baseline")
    env["PYTHONPATH"] = str(work)
    env["PERFCHECK_MUTANT_ROOT"] = str(work / "mutants")
    env["PERFCHECK_MUTATION_RECEIPTS"] = str(output / "imports.jsonl")
    executable = str(Path(sys.executable).parent / "mutmut")
    try:
        result = run_child(
            Command((executable, "run", "--max-children", "1"), work, env),
            output / "run.log",
            BUDGET,
        )
        for name, args in (
            ("results.txt", ("results", "--all", "true")),
            ("export.log", ("export-cicd-stats",)),
        ):
            exported = run_child(
                Command((executable, *args), work, env), output / name, 30
            )
            if not result.timed_out:
                check_phase(exported, name)
    finally:
        if (work / "mutants").exists():
            _ = shutil.copytree(work / "mutants", output / "mutants")
    if not result.timed_out:
        verify_experiment(output, work / "mutants", result.returncode)
        inspect_mutants(work, output, env)
    return result
