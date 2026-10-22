from __future__ import annotations

import importlib.util
import re
import sys
from itertools import combinations
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import pytest
from examples._support import run_local_command

_ROOT: Final = Path(__file__).resolve().parents[1]
_LESSON: Final = _ROOT / "examples/10-comparative-methods.py"
_BOUNDARY: Final = "does not determine perfcheck PASS/FAIL"


@pytest.fixture(scope="module")
def comparative_output() -> str:
    if importlib.util.find_spec("marimo") is None:
        pytest.skip("comparative lesson requires the optional examples group")
    # Given: a genuine temporary cwd containing a misleading stale result.
    with TemporaryDirectory(prefix="perfcheck-task6-") as directory:
        workspace = Path(directory)
        _ = (workspace / "stale.txt").write_text(
            "Welch t=999; determines a perfcheck verdict", encoding="utf-8"
        )
        # When: the absolute managed interpreter executes the actual lesson there.
        result = run_local_command(
            (sys.executable, str(_LESSON)), cwd=workspace, timeout_seconds=15.0
        )
        # Then: success must include fresh calculated evidence, not just exit zero.
        assert result.returncode == 0, result.stderr
        assert "Welch t=999" not in result.stdout
        assert tuple(path.name for path in workspace.iterdir()) == ("stale.txt",)
    _ = sys.stdout.write(result.stdout)
    return result.stdout


def test_comparative_receipt_has_ordered_sections(comparative_output: str) -> None:
    # Given: the fresh isolated lesson receipt.
    # When: the learner reads its teaching sections.
    positions = tuple(
        comparative_output.index(section)
        for section in ("Goal:", "Inputs:", "Run:", "Evidence:", "Takeaway:")
    )
    # Then: the complete narrative is present in order.
    assert positions == tuple(sorted(positions))


@pytest.mark.parametrize(
    "method", ["Welch", "Permutation", "Mann--Whitney", "Bayesian"]
)
def test_each_method_prints_its_local_nonverdict_boundary(
    comparative_output: str, method: str
) -> None:
    # Given: an isolated receipt with four method-specific evidence lines.
    # When: one method's line is inspected independently.
    row = next(
        line
        for line in comparative_output.splitlines()
        if line.startswith(f"Evidence: {method}")
    )
    # Then: a numerical result cannot be mistaken for a product verdict.
    assert _BOUNDARY in row
    assert "does not change product policy" in row
    assert "Question:" in row
    assert "Assumptions:" in row
    assert "dataset=" in row


def test_welch_statistic_matches_unpooled_standard_error(
    comparative_output: str,
) -> None:
    # Given: current (4, 5, 6), baseline (1, 2, 3), each sample variance 1.
    # When: the Welch statistic and approximate degrees of freedom are read.
    match = re.search(r"Welch t=([\d.]+); df=([\d.]+)", comparative_output)
    assert match is not None
    # Then: t = 3 / sqrt(1/3 + 1/3), df = 4; no tail probability is claimed.
    assert tuple(float(value) for value in match.groups()) == pytest.approx(
        (3 / (2 / 3) ** 0.5, 4.0), abs=1e-6
    )
    assert "Welch p-value not reported" in comparative_output


def test_seeded_permutation_reports_its_small_monte_carlo_experiment(
    comparative_output: str,
) -> None:
    # Given: a greater-tail mean-difference experiment with 15 random relabelings.
    # When: its seeded receipt is read.
    # Then: its observed statistic, draw contract and coarse resolution are explicit.
    assert "observed=3.000; seed=42; draws=15" in comparative_output
    assert "extreme=1; Monte Carlo p=0.125000" in comparative_output
    match = re.search(r"null=\(([^)]+)\)", comparative_output)
    assert match is not None
    assert tuple(float(value) for value in match[1].split(",")) == pytest.approx(
        (
            -1 / 3,
            1,
            1 / 3,
            1,
            -1,
            1,
            -1 / 3,
            3,
            7 / 3,
            -1 / 3,
            1 / 3,
            -3,
            1 / 3,
            -5 / 3,
            -1 / 3,
        )
    )
    assert "Monte Carlo" in comparative_output
    assert "resolution=1/16" in comparative_output
    assert "exchangeability" in comparative_output


def test_exact_permutation_reference_exposes_monte_carlo_limits() -> None:
    # Given: all twenty allocations of the six fixed observations to groups of three.
    allocations = tuple(combinations(range(1, 7), 3))
    # When: the mean difference is evaluated for every allocation independently.
    differences = tuple((2 * sum(group) - 21) / 3 for group in allocations)
    # Then: only one allocation reaches 3; the exact tail 1/20 differs from 2/16.
    assert len(differences) == 20
    assert sum(difference >= 3 for difference in differences) / 20 == 0.05


def test_tied_ranks_agree_with_pairwise_mann_whitney_score(
    comparative_output: str,
) -> None:
    # Given: current (2, 3, 3), baseline (1, 2, 4), with a cross-group tie at 2.
    # When: average ranks and current-sample U are read.
    # Then: pooled ranks sum to 21 and U = wins + half ties = 5 + 0.5.
    assert "ranks=(2.5, 4.5, 4.5, 1.0, 2.5, 6.0)" in comparative_output
    assert "rank_sum=11.500; U=5.500; pairwise_score=0.611111" in comparative_output
    assert "not automatically a median test" in comparative_output


def test_beta_posterior_is_conditional_on_bernoulli_model(
    comparative_output: str,
) -> None:
    # Given: three exceedances and one non-exceedance with a uniform Beta(1, 1) prior.
    # When: the conjugate posterior receipt is read.
    # Then: Beta(4, 2) has mean 2/3 and tail 1 - (5/16 - 4/32) = 13/16.
    assert (
        "posterior=Beta(4,2); mean=0.666667; Pr(theta>0.5)=0.812500"
        in comparative_output
    )
    assert "Bernoulli" in comparative_output
    assert "prior=Beta(1,1)" in comparative_output


def test_comparative_receipt_repeats_without_workspace_artifacts(
    comparative_output: str, tmp_path: Path
) -> None:
    # Given: an empty, independent temporary cwd, not the stale-output workspace.
    protected = (
        _ROOT / "README.md",
        _ROOT / "AGENTS.md",
        _ROOT / "docs/conf.py",
        _ROOT / "pyproject.toml",
        _ROOT / "uv.lock",
        *sorted((_ROOT / "src").rglob("*.py")),
        *sorted((_ROOT / "examples").glob("0[1-9]-*.py")),
    )
    before = tuple(path.read_bytes() for path in protected)
    # When: the same lesson executes again with its explicit seed.
    result = run_local_command(
        (sys.executable, str(_LESSON)), cwd=tmp_path, timeout_seconds=15.0
    )
    # Then: full stdout repeats and the lesson leaves no persisted result.
    assert result.returncode == 0, result.stderr
    assert result.stdout == comparative_output
    assert tuple(tmp_path.iterdir()) == ()
    assert tuple(path.read_bytes() for path in protected) == before
