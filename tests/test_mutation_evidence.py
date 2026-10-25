import json
import sys
from typing import TYPE_CHECKING, Literal, assert_never

import pytest
from tools.mutation_evidence import (
    EvidenceError,
    Inventory,
    NativeStats,
    check_phase,
    verify_experiment,
)
from tools.mutation_process import Command, run_child

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def experiment(tmp_path: Path) -> Path:
    tree = tmp_path / "mutants"
    source = tree / "src/perfcheck/regression_aggregation.py"
    source.parent.mkdir(parents=True)
    _ = source.write_text("def aggregate_status(): return True\n")
    inventory = Inventory(
        exit_code_by_key={
            "perfcheck.regression_aggregation.x_status__mutmut_1": 1,
            "perfcheck.regression_aggregation.x_status__mutmut_2": 0,
        },
        hash_by_function_name={},
        type_check_error_by_key={},
        durations_by_key={},
        estimated_durations_by_key={},
    )
    _ = source.with_suffix(".py.meta").write_text(inventory.model_dump_json())
    stats = NativeStats(
        killed=1,
        survived=1,
        total=2,
        no_tests=0,
        skipped=0,
        suspicious=0,
        timeout=0,
        check_was_interrupted_by_user=0,
        segfault=0,
    )
    _ = (tree / "mutmut-cicd-stats.json").write_text(stats.model_dump_json())
    _ = (tmp_path / "imports.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "module_file": str(source),
                    "nodeid": "tests/test_suite_aggregation.py::test_x",
                    "pid": 1,
                    "mutant": mutant,
                }
            )
            for mutant in inventory.exit_code_by_key
        )
        + "\n"
    )
    _ = (tmp_path / "run.log").write_text(
        "Running clean tests\nRunning forced fail test\nRunning mutation testing\n"
    )
    _ = (tmp_path / "results.txt").write_text(
        "\n".join(
            f"{key}: {'killed' if code else 'survived'}"
            for key, code in inventory.exit_code_by_key.items()
        )
    )
    return tmp_path


def test_completed_survivor_is_advisory(experiment: Path) -> None:
    # Given: complete, reconciled evidence containing a survivor.
    # When: the actual runner evidence validator processes it.
    verify_experiment(experiment, experiment / "mutants", 0)
    # Then: evidence is valid without imposing a mutation score gate.
    assert (experiment / "outcomes.json").is_file()


@pytest.mark.parametrize(
    "mode",
    [
        "missing",
        "empty",
        "malformed",
        "extra-target",
        "syntax-skip",
        "internal-error",
        "wrong-total",
    ],
)
def test_invalid_experiment_fails_closed(
    experiment: Path,
    mode: Literal[
        "missing",
        "empty",
        "malformed",
        "extra-target",
        "syntax-skip",
        "internal-error",
        "wrong-total",
    ],
) -> None:
    # Given: evidence corrupted at a boundary the runner relies on.
    tree = experiment / "mutants"
    meta = tree / "src/perfcheck/regression_aggregation.py.meta"
    match mode:
        case "missing":
            meta.unlink()
        case "empty":
            inventory = Inventory.model_validate_json(meta.read_text())
            inventory.exit_code_by_key.clear()
            _ = meta.write_text(inventory.model_dump_json())
        case "malformed":
            _ = (tree / "mutmut-cicd-stats.json").write_text("invalid")
        case "extra-target":
            _ = (tree / "other.py.meta").write_text(meta.read_text())
        case "syntax-skip":
            with (experiment / "run.log").open("a") as log:
                _ = log.write("Unsupported syntax in target, skipping")
        case "internal-error":
            inventory = Inventory.model_validate_json(meta.read_text())
            inventory.exit_code_by_key[next(iter(inventory.exit_code_by_key))] = 3
            _ = meta.write_text(inventory.model_dump_json())
        case "wrong-total":
            stats_file = tree / "mutmut-cicd-stats.json"
            stats = NativeStats.model_validate_json(stats_file.read_text())
            _ = stats_file.write_text(
                stats.model_copy(update={"total": 3}).model_dump_json()
            )
        case _:
            assert_never(mode)
    # When: the exact pilot validator checks the corrupted receipt.
    with pytest.raises((EvidenceError, ValueError)):
        verify_experiment(experiment, tree, 0)
    # Then: stale-looking successful counters cannot establish compatibility.


@pytest.mark.skipif(sys.platform == "win32", reason="Unix bounded pilot")
def test_real_failing_baseline_cannot_reach_mutation(tmp_path: Path) -> None:
    # Given: an isolated pytest baseline with an actual failing assertion.
    _ = (tmp_path / "test_baseline.py").write_text(
        "def test_baseline(): assert False\n"
    )
    # When: it completes through the same subprocess boundary as the pilot.
    result = run_child(
        Command((sys.executable, "-m", "pytest", "test_baseline.py"), tmp_path),
        tmp_path / "baseline.log",
        30,
    )
    # Then: the runner's prerequisite guard rejects it with its phase identified.
    assert result.returncode == 1
    with pytest.raises(EvidenceError, match="clean selected baseline"):
        check_phase(result, "clean selected baseline")
