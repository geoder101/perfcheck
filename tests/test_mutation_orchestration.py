import json
import shutil
from importlib.metadata import PackageNotFoundError
from typing import TYPE_CHECKING, Literal

import pytest
from tools import mutation_campaign, mutation_runner
from tools.mutation_evidence import EvidenceError, Inventory, NativeStats
from tools.mutation_process import ChildResult, Command

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

type Mode = Literal[
    "valid",
    "baseline",
    "timeout",
    "malformed",
    "inventory",
    "imports",
    "inspection",
    "export",
    "source-change",
]


def _child(mode: Mode, root: Path) -> Callable[[Command, Path, float], ChildResult]:
    def child(command: Command, log: Path, _budget: float) -> ChildResult:
        output = log.parent
        if log.name == "baseline.log" and mode == "baseline":
            return ChildResult(1, timed_out=False)
        if log.name == "run.log":
            _write_campaign(command.cwd, output)
            _ = log.write_text(
                """Running clean tests
Running forced fail test
Running mutation testing
"""
            )
            if mode == "source-change":
                _ = (root / mutation_campaign.TARGET).write_text("VALUE = 2\n")
            return ChildResult(0, timed_out=mode == "timeout")
        if log.name == "export.log":
            tree = command.cwd / "mutants"
            if mode == "malformed":
                _ = (tree / "mutmut-cicd-stats.json").write_text("malformed")
            if mode == "inventory":
                (tree / f"{mutation_campaign.TARGET}.meta").unlink()
            if mode == "imports":
                (output / "imports.jsonl").unlink()
            if mode == "export":
                return ChildResult(7, timed_out=False)
        return ChildResult(0, timed_out=False)

    return child


def _write_campaign(work: Path, output: Path) -> None:
    tree = work / "mutants"
    _ = shutil.copytree(work / "src", tree / "src")
    source = tree / mutation_campaign.TARGET
    keys = (
        "perfcheck.regression_aggregation.x_status__mutmut_1",
        "perfcheck.regression_aggregation.x_status__mutmut_2",
    )
    inventory = Inventory(
        exit_code_by_key=dict(zip(keys, (1, 0), strict=True)),
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
    _ = (output / "imports.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "module_file": str(source),
                    "nodeid": "tests/test_suite_aggregation.py::test_x",
                    "pid": 1,
                    "mutant": key,
                }
            )
            for key in keys
        )
        + "\n"
    )
    _ = (output / "results.txt").write_text(f"{keys[0]}: killed\n{keys[1]}: survived\n")


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    # Command-doubled orchestration is portable; native preflight has separate tests.
    def accepted(output: Path) -> bool:
        output.mkdir(parents=True)
        return True

    monkeypatch.setattr(mutation_runner, "prepare_output", accepted)
    root = tmp_path / "project"
    (root / "src/perfcheck").mkdir(parents=True)
    _ = (root / mutation_campaign.TARGET).write_text("VALUE = 1\n")
    for name in ("tests", "tools"):
        (root / name).mkdir()
    for name in ("pyproject.toml", "uv.lock", "README.md"):
        _ = (root / name).write_text("")
    return root


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("valid", "complete"),
        ("baseline", "invalid"),
        ("timeout", "incomplete"),
        ("malformed", "invalid"),
        ("inventory", "invalid"),
        ("imports", "invalid"),
        ("inspection", "invalid"),
        ("export", "invalid"),
        ("source-change", "invalid"),
    ],
)
def test_real_runner_persists_status(
    root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: Mode,
    expected: str,
) -> None:
    # Given: deterministic native-command doubles at the expensive external seam.
    output = tmp_path / "evidence"

    def version(_name: str) -> str:
        return "controlled"

    def inspection(_work: Path, evidence: Path, _environment: dict[str, str]) -> None:
        _ = (evidence / "inspection-imports.jsonl").write_text("inspection-only")
        if mode == "inspection":
            message = "controlled inspection failure"
            raise EvidenceError(message)

    monkeypatch.setattr(mutation_runner, "version", version)
    monkeypatch.setattr(mutation_campaign, "run_child", _child(mode, root))
    monkeypatch.setattr(mutation_campaign, "inspect_mutants", inspection)
    # When: the real runner executes its complete snapshot/evidence/status path.
    code = mutation_runner.run_pilot(root, output)
    # Then: only reconciled survivor-containing evidence returns success.
    assert code == (0 if expected == "complete" else 1)
    assert json.loads((output / "status.json").read_text())["status"] == expected
    if mode == "baseline":
        assert not (output / "run.log").exists()
    else:
        assert (output / "mutants").is_dir()
    if mode == "imports":
        assert not (output / "inspection-imports.jsonl").exists()


def test_missing_optional_package_retains_invalid_receipt(
    root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an environment that did not install the optional mutation group.
    def missing(_name: str) -> str:
        package = "mutmut"
        raise PackageNotFoundError(package)

    monkeypatch.setattr(mutation_runner, "version", missing)
    output = tmp_path / "evidence"
    # When: the runner accepts a fresh output directory then initializes.
    code = mutation_runner.run_pilot(root, output)
    # Then: initialization failure is nonzero with a readable invalid receipt.
    assert code == 1
    assert json.loads((output / "status.json").read_text())["status"] == "invalid"


def test_missing_source_retains_invalid_receipt(root: Path, tmp_path: Path) -> None:
    # Given: a source input missing before initialization.
    (root / mutation_campaign.TARGET).unlink()
    output = tmp_path / "evidence"
    # When: the accepted experiment initializes.
    code = mutation_runner.run_pilot(root, output)
    # Then: missing input cannot bypass the failure status receipt.
    assert code == 1
    assert json.loads((output / "status.json").read_text())["status"] == "invalid"
