from statistics import NormalDist

import pytest
from examples import _power as power


@pytest.mark.parametrize(
    ("value", "expected"), [(0.0, 0.5), (-2.0, 0.0227501319481792)]
)
def test_normal_cdf_when_known_oracle(value: float, expected: float) -> None:
    # Given: standard normal oracle points.
    # When: the lower-tail probability is evaluated.
    actual = power.normal_cdf(value)
    # Then: the continuous tail agrees to numerical precision.
    assert actual == pytest.approx(expected, abs=1e-15)


def test_z_when_known_sigma_uses_population_standard_error() -> None:
    # Given: null mean 100, known sigma 10, n=25 and observed mean 96.
    # When: the lower-tailed z result is calculated.
    result = power.known_sigma_z(96.0)
    # Then: SE=2, z=-2 and p is the lower normal tail.
    assert result.standard_error == 2.0
    assert result.z == -2.0
    assert result.p == pytest.approx(0.0227501319481792)


def test_power_when_null_effect_equals_alpha() -> None:
    # Given: a prespecified right-tailed normal mean test under the null.
    experiment = power.PowerExperiment(effect=0.0, alpha=0.05)
    # When: rejection probability is calculated analytically.
    result = power.analytic_power(experiment)
    # Then: its size is alpha, not zero.
    assert result.power == pytest.approx(experiment.alpha)
    assert result.beta == pytest.approx(0.95)


def test_power_when_alternative_at_critical_mean_is_half() -> None:
    # Given: an alternative centered exactly on the rejection threshold.
    shift = NormalDist().inv_cdf(0.95) * 2
    # When: the right-tail rejection probability is calculated.
    result = power.analytic_power(power.PowerExperiment(effect=shift))
    # Then: symmetry puts half the alternative distribution in either region.
    assert result.power == pytest.approx(0.5)
    assert result.beta == pytest.approx(0.5)


def test_null_simulation_when_seeded_separates_models() -> None:
    # Given: 512 independently generated null statistics per explicit model.
    experiment = power.NullExperiment(repetitions=512, seed=42)
    # When: p-values are generated using each specified reference model.
    result = power.null_pvalues(experiment)
    # Then: rounding up is conservative; using sigma/2 is anti-conservative.
    assert result == power.null_pvalues(experiment)
    assert all(d >= c for c, d in zip(result.continuous, result.discrete, strict=True))
    assert sum(p <= 0.05 for p in result.violated) > sum(
        p <= 0.05 for p in result.continuous
    )
    assert all(0 <= p <= 1 for p in result.continuous)
