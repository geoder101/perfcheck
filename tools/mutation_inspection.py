"""Visible reruns distinguishing assertion kills from infrastructure failures."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from tools.mutation_evidence import read_inventory, require
from tools.mutation_process import Command, run_child


def inspect_mutants(work: Path, output: Path, environment: dict[str, str]) -> None:
    """Replay generated originals, forced failure, a kill, and any survivor."""
    tree = work / "mutants"
    inventory = read_inventory(tree)
    env = {
        **environment,
        "PYTHONPATH": os.pathsep.join((str(tree / "src"), str(tree))),
        "PERFCHECK_MUTATION_RECEIPTS": str(output / "inspection-imports.jsonl"),
    }
    argv = (
        sys.executable,
        "-m",
        "pytest",
        "-p",
        "no:pytest_cov",
        "-p",
        "tools.mutation_probe",
        "-vv",
        "--tb=long",
        "tests/test_suite_aggregation.py",
    )
    for name, mutant, expected in (
        ("generated-baseline", "", 0),
        ("forced-failure", "fail", 1),
    ):
        result = run_child(
            Command(argv, tree, {**env, "MUTANT_UNDER_TEST": mutant}),
            output / f"{name}.log",
            15,
        )
        require(
            result.returncode == expected and not result.timed_out,
            f"invalid {name} rerun",
        )
    require(
        "MutmutProgrammaticFailException"
        in (output / "forced-failure.log").read_text(),
        "forced failure did not execute the mutmut trampoline",
    )
    inspected: dict[str, str] = {}
    executable = str(Path(sys.executable).parent / "mutmut")
    for verdict, code in (("killed", 1), ("survived", 0)):
        candidates = [
            key for key, value in inventory.exit_code_by_key.items() if value == code
        ]
        for index, mutant in enumerate(candidates[:3]):
            log = output / f"inspect-{verdict}-{index}.log"
            result = run_child(
                Command(argv, tree, {**env, "MUTANT_UNDER_TEST": mutant}), log, 15
            )
            require(
                result.returncode == code and not result.timed_out,
                f"mutant rerun changed verdict: {mutant}",
            )
            assertion_killed = code == 1 and "AssertionError" in log.read_text()
            if code == 0 or assertion_killed:
                inspected[verdict] = mutant
                shown = run_child(
                    Command((executable, "show", mutant), work, environment),
                    output / f"inspect-{verdict}.diff",
                    10,
                )
                require(shown.returncode == 0, "mutant diff export failed")
                break
        require(
            not candidates or verdict in inspected,
            f"no assertion-level {verdict} inspection",
        )
    require("killed" in inspected, "no assertion-killed mutant to inspect")
    _ = (output / "inspection.json").write_text(json.dumps(inspected, indent=2))
