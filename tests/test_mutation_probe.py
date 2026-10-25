import json
import os
import sys
from pathlib import Path

import pytest
from tools.mutation_process import Command, run_child


@pytest.mark.skipif(sys.platform == "win32", reason="Unix pilot subprocess")
@pytest.mark.parametrize("allowed", [True, False])
def test_probe_checks_import_during_real_test_call(
    tmp_path: Path, allowed: bool
) -> None:
    # Given: a selected test importing a disposable aggregation module.
    package = tmp_path / "perfcheck"
    package.mkdir()
    _ = (package / "__init__.py").write_text("")
    source = package / "regression_aggregation.py"
    _ = source.write_text("VALUE = 42\n")
    _ = (tmp_path / "test_selected.py").write_text(
        """from perfcheck.regression_aggregation import VALUE
def test_selected():
    assert VALUE == 42
"""
    )
    root = tmp_path if allowed else tmp_path / "mutants"
    root.mkdir(exist_ok=True)
    receipt = tmp_path / "imports.jsonl"
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join((str(tmp_path), str(Path(__file__).parents[1]))),
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PERFCHECK_MUTANT_ROOT": str(root),
        "PERFCHECK_MUTATION_RECEIPTS": str(receipt),
    }
    # When: pytest actually executes the test with the opt-in probe loaded.
    result = run_child(
        Command(
            (
                sys.executable,
                "-m",
                "pytest",
                "-p",
                "tools.mutation_probe",
                "test_selected.py",
            ),
            tmp_path,
            env,
        ),
        tmp_path / "log",
        30,
    )
    # Then: only an allowed source tree yields a successful test and import receipt.
    assert result.returncode == (0 if allowed else 1)
    if allowed:
        assert json.loads(receipt.read_text())["module_file"] == str(source)
    else:
        assert "escaped mutant tree" in (tmp_path / "log").read_text()
