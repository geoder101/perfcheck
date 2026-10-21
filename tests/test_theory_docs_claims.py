from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]


def _read(relative_path: Path) -> str:
    return (_ROOT / relative_path).read_text(encoding="utf-8")


def _assert_no_prohibited_p_value_claim(source: str) -> None:
    assert (
        re.search(
            r"\bperfcheck calculate(?:s)? (?:a )?p-?value(?:s)?\b",
            source,
            flags=re.IGNORECASE,
        )
        is None
    )


def test_measurement_page_documents_supported_calculations_with_examples() -> None:
    # Given: the per-run measurement chapter read by a documentation user.
    measurement = _read(Path("docs/measurement-and-summaries.rst"))

    # When: the user looks for every implemented summary convention.

    # Then: the chapter names all supported statistics and bounded examples.
    required_terms = (
        "``math.fsum``",
        "``mean``",
        "``p50``",
        "``p90``",
        "``p95``",
        "``p99``",
        "``min``",
        "``max``",
        "``std``",
        "``first``",
        "``last``",
        "``delta``",
        "``slope``",
        "``linear`` method",
        "sample standard deviation with Bessel correction",
        "Worked example",
        "20 / 4 = 5",
        "P50 has",
        "P90 has",
        "0.3(6)+0.7(8)=7.4",
        "min = 2 and max = 8",
        "\\sqrt{8/(3-1)}=2",
        "first = 2,\n   last = 8, and delta",
        "slope = :math:`25/50=0.5`",
    )
    assert all(term in measurement for term in required_terms)


def test_eligibility_page_documents_all_fields_and_no_imputation_contract() -> None:
    # Given: the eligibility chapter read before interpreting a comparison.
    eligibility = _read(Path("docs/eligibility-and-comparability.rst"))

    # When: the user checks the implemented quality boundaries.

    # Then: every policy field, gap rule, and non-imputation consequence is named.
    required_terms = (
        "``warmup_seconds``",
        "``cooldown_seconds``",
        "``min_analysis_window_seconds``",
        "``min_points``",
        "``min_coverage``",
        "``max_gap_steps``",
        "maximum permitted duration",
        "``gap_too_large``",
        "``analysis_window_too_short``",
        "``insufficient_points``",
        "``coverage_too_low``",
        "Worked example",
        "does not impute, interpolate, carry forward, or synthesize",
        "no summary value is written",
    )
    assert all(term in eligibility for term in required_terms)


def test_comparison_and_decision_pages_document_supported_boundaries() -> None:
    # Given: the comparison and verdict chapters read together.
    comparison = _read(Path("docs/uncertainty-and-comparison.rst"))
    decisions = _read(Path("docs/decisions-and-limitations.rst"))

    # When: a reader checks method selection, bounds, and verdict semantics.

    # Then: the documented implementation terms retain their precise boundaries.
    comparison_terms = (
        "lower-is-worse",
        "``nominal_alpha``",
        "Bonferroni effective alpha",
        "with replacement",
        "``PCG64``",
        '``method="linear"``',
        "``reference_anomaly``",
        "advisory evidence only",
        "remains ``INCONCLUSIVE``",
    )
    decision_terms = (
        "equality passes",
        "``PASS``, not ``FAIL``",
        "Suite aggregation",
        "**perfcheck does not implement t-tests, Welch tests, F-tests, or p-values.**",
    )
    assert all(term in comparison for term in comparison_terms)
    assert all(term in decisions for term in decision_terms)


def test_classical_methods_remain_explicitly_unsupported() -> None:
    # Given: the comparison chapters and the classical contrast lesson.
    source = "\n".join(
        (
            _read(Path("docs/uncertainty-and-comparison.rst")),
            _read(Path("docs/decisions-and-limitations.rst")),
            _read(Path("examples/08-bootstrap-and-decisions.py")),
        )
    )

    # When: their p-value terminology is checked.
    _assert_no_prohibited_p_value_claim(source)

    # Then: the implemented boundary remains explicit to learners.
    assert "These percentile-bootstrap bounds are not p-values." in source
    assert "p-value not computed" in source


def test_classical_methods_reject_a_prohibited_p_value_claim() -> None:
    # Given: an otherwise valid source containing an unsupported positive claim.
    prohibited_source = "perfcheck calculates a p-value."

    # When: the claim boundary validates that source.

    # Then: the prohibited implication is rejected.
    with pytest.raises(AssertionError):
        _assert_no_prohibited_p_value_claim(prohibited_source)
