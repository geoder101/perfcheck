import pytest
from examples import _multiple_testing as multiple


def test_family_when_twenty_independent_true_nulls_inflates_error() -> None:
    # Given: independent size-.05 tests, all twenty nulls true.
    # When: the analytic probability of any false rejection is evaluated.
    result = multiple.independent_fwer(20, 0.05)
    # Then: family-wise error is about .641514, not .05.
    assert result == pytest.approx(0.6415140775914581)


def test_bonferroni_when_twenty_tests_divides_alpha() -> None:
    # Given: a p-value right on the .05/20 boundary.
    values = (0.0025,) + (1.0,) * 19
    # When: the Bonferroni adjustment is calculated.
    result = multiple.adjust_pvalues(values, "Bonferroni")
    # Then: adjusted p=.05 gives an inclusive rejection boundary.
    assert 0.05 / 20 == 0.0025
    assert result[0] == 0.05


@pytest.mark.parametrize(
    ("method", "expected"),
    [
        ("none", (0.04, 0.001, 0.03, 0.2)),
        ("Bonferroni", (0.16, 0.004, 0.12, 0.8)),
        ("Holm", (0.09, 0.004, 0.09, 0.2)),
        ("BH", (0.04 * 4 / 3, 0.004, 0.04 * 4 / 3, 0.2)),
    ],
)
def test_adjustments_when_unsorted_restore_original_order(
    method: multiple.Method, expected: tuple[float, ...]
) -> None:
    # Given: a fixed unsorted family, not a simulated truth claim.
    values = (0.04, 0.001, 0.03, 0.2)
    # When: each named multiplicity procedure adjusts the family.
    result = multiple.adjust_pvalues(values, method)
    # Then: step-down/step-up monotonicity and original indices are preserved.
    assert result == pytest.approx(expected)


def test_family_when_all_nulls_false_has_zero_false_discoveries() -> None:
    # Given: independent normal tests with every null false.
    experiment = multiple.FamilyExperiment(size=20, true_nulls=0, repetitions=128)
    # When: the seeded family experiment runs.
    result = multiple.simulate_families(experiment)
    # Then: rejections cannot be false positives; realized FDP and FWER are zero.
    assert result.fwer == 0.0
    assert result.mean_fdp == 0.0
    assert all(row.false_rejections == 0 for row in result.families)


def test_family_when_seeded_has_reproducible_adjusted_decisions() -> None:
    # Given: independent mixed true/false nulls, with a bounded teaching budget.
    experiment = multiple.FamilyExperiment(method="Holm", repetitions=512)
    # When: the entire experiment is repeated.
    result = multiple.simulate_families(experiment)
    # Then: truth labels, adjusted decisions and empirical uncertainty repeat.
    assert result == multiple.simulate_families(experiment)
    first = result.families[0]
    assert first.rejected == tuple(p <= experiment.alpha for p in first.adjusted)
    assert first.fdp == first.false_rejections / max(1, sum(first.rejected))
    assert result.fwer_mc_se >= 0


@pytest.mark.parametrize(("size", "repetitions"), [(41, 128), (20, 513)])
def test_family_when_budget_exceeded_rejects(size: int, repetitions: int) -> None:
    # Given: an oversized interactive experiment.
    # When: its inputs are constructed.
    with pytest.raises(ValueError, match=r"size|repetitions"):
        _ = multiple.FamilyExperiment(size=size, repetitions=repetitions)
    # Then: no uncontrolled simulation can run.
