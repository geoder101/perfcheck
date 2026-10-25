"""Fail-closed parsing of optional mutation experiment evidence."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, Literal, override

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from tools.mutation_process import ChildResult


@dataclass(frozen=True, slots=True)
class EvidenceError(Exception):
    """A specific missing or invalid evidence requirement."""

    detail: str

    @override
    def __str__(self) -> str:
        """Render the failed evidence requirement for the status receipt."""
        return self.detail


def require(condition: bool, detail: str) -> None:
    """Reject an unmet experiment validity requirement."""
    if not condition:
        raise EvidenceError(detail)


def check_phase(result: ChildResult, name: str) -> None:
    """Reject failed prerequisites before evaluating mutants."""
    require(
        result.returncode == 0 and not result.timed_out, f"{name} failed; see its log"
    )


class ImportReceipt(BaseModel):
    """One observation taken during actual selected test execution."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, extra="forbid")
    module_file: str
    nodeid: str
    mutant: str
    pid: int = Field(gt=0)


def completion(
    code: int, *, timed_out: bool
) -> Literal["complete", "invalid", "incomplete"]:
    """Never equate a timeout or failing child with completed evidence."""
    if timed_out:
        return "incomplete"
    return "complete" if code == 0 else "invalid"


def read_imports(path: Path, mutant_root: Path) -> tuple[ImportReceipt, ...]:
    """Require actual selected-test observations inside the generated source tree."""
    imports = tuple(
        ImportReceipt.model_validate_json(line)
        for line in path.read_text().splitlines()
    )
    require(bool(imports), "missing selected-test import receipts")
    for receipt in imports:
        require(
            Path(receipt.module_file).resolve()
            == (mutant_root / "src/perfcheck/regression_aggregation.py").resolve(),
            "aggregation import escaped mutant tree",
        )
        require(
            receipt.nodeid.startswith("tests/test_suite_aggregation.py::"),
            "unexpected test selection in import receipt",
        )
    return imports


class NativeStats(BaseModel):
    """The exact aggregate export schema of mutmut 3.8.0."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        frozen=True, strict=True, extra="forbid"
    )
    killed: int = Field(ge=0)
    survived: int = Field(ge=0)
    total: int = Field(ge=0)
    no_tests: int = Field(ge=0)
    skipped: int = Field(ge=0)
    suspicious: int = Field(ge=0)
    timeout: int = Field(ge=0)
    check_was_interrupted_by_user: int = Field(ge=0)
    segfault: int = Field(ge=0)


class Inventory(BaseModel):
    """Preserve raw verdict codes, including pytest internal errors."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True, strict=True)
    exit_code_by_key: dict[str, int | None]
    hash_by_function_name: dict[str, str]
    type_check_error_by_key: dict[str, str | None]
    durations_by_key: dict[str, float]
    estimated_durations_by_key: dict[str, float]


def read_stats(path: Path) -> NativeStats:
    """Reject zero inventory and malformed native aggregate exports."""
    stats = NativeStats.model_validate_json(path.read_text())
    require(stats.total > 0, "zero generated mutants")
    return stats


def read_inventory(root: Path) -> Inventory:
    """Scan fail-closed and reject any mutation outside the approved target."""
    metadata: list[Path] = []

    def scan_error(error: OSError) -> None:
        raise error

    for directory, _, files in root.walk(on_error=scan_error):
        metadata.extend(directory / name for name in files if name.endswith(".meta"))
    require(
        metadata == [root / "src/perfcheck/regression_aggregation.py.meta"],
        "missing or unexpected mutation target inventory",
    )
    inventory = Inventory.model_validate_json(metadata[0].read_text())
    require(bool(inventory.exit_code_by_key), "zero generated mutants")
    require(
        all(
            key.startswith("perfcheck.regression_aggregation.")
            for key in inventory.exit_code_by_key
        ),
        "unexpected mutant identifier",
    )
    return inventory


def verify_experiment(output: Path, original_tree: Path, code: int) -> None:
    """Reconcile native counters with raw outcomes and actual test imports."""
    require(code == 0, f"mutmut child failed with exit {code}; see run.log")
    tree = output / "mutants"
    stats = read_stats(tree / "mutmut-cicd-stats.json")
    inventory = read_inventory(tree)
    codes = Counter(inventory.exit_code_by_key.values())
    expected = {
        "killed": codes[1] + codes[3],
        "survived": codes[0],
        "total": len(inventory.exit_code_by_key),
        "no_tests": codes[5] + codes[33],
        "skipped": codes[34],
        "suspicious": codes[35],
        "timeout": sum(codes[key] for key in (36, -24, 24, 152, 255)),
        "check_was_interrupted_by_user": codes[2],
        "segfault": codes[-11] + codes[-9],
    }
    require(stats.model_dump() == expected, "native export does not reconcile")
    require(
        all(code in {0, 1, 36, -24, 24, 152, 255} for code in codes),
        "invalid infrastructure outcomes; raw codes retained in inventory",
    )
    results = (output / "results.txt").read_text()
    for key, raw_code in inventory.exit_code_by_key.items():
        if raw_code in {0, 1}:
            verdict = "survived" if raw_code == 0 else "killed"
            require(f"{key}: {verdict}" in results, "text results do not reconcile")
    imports = read_imports(output / "imports.jsonl", original_tree)
    require(
        set(inventory.exit_code_by_key).issubset(
            {receipt.mutant for receipt in imports}
        ),
        "missing campaign import observation for an inventoried mutant",
    )
    log = (output / "run.log").read_text()
    for phase in (
        "Running clean tests",
        "Running forced fail test",
        "Running mutation testing",
    ):
        require(phase in log, f"missing {phase} evidence")
    require("Unsupported syntax" not in log, "unsupported syntax skipped")
    _ = (output / "outcomes.json").write_text(
        json.dumps(
            {
                "raw_exit_codes": inventory.exit_code_by_key,
                "assertion_candidate_killed": codes[1],
                "pytest_internal_error": codes[3],
                "unchecked": codes[None],
                "type_check_caught": codes[37],
                "native": stats.model_dump(),
            },
            indent=2,
        )
    )
