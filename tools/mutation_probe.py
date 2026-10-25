"""Opt-in pytest hook proving imports from actual selected mutant tests."""

import importlib
import json
import os
from pathlib import Path

import pytest


def pytest_runtest_call(item: pytest.Item) -> None:
    """Record the resolved aggregation module at the selected test call boundary."""
    root = Path(os.environ["PERFCHECK_MUTANT_ROOT"]).resolve(strict=True)
    module = importlib.import_module("perfcheck.regression_aggregation")
    if module.__file__ is None:
        pytest.fail("aggregation module has no source path")
    source = Path(module.__file__).resolve(strict=True)
    if not source.is_relative_to(root):
        pytest.fail(f"aggregation import escaped mutant tree: {source}")
    receipt = {
        "module_file": str(source),
        "nodeid": item.nodeid,
        "mutant": os.environ.get("MUTANT_UNDER_TEST", ""),
        "pid": os.getpid(),
    }
    with Path(os.environ["PERFCHECK_MUTATION_RECEIPTS"]).open("a") as output:
        _ = output.write(json.dumps(receipt) + "\n")
