from __future__ import annotations

import re
from pathlib import Path
from typing import Final

import pytest

_ROOT: Final = Path(__file__).parents[1]
_COMPARATIVE_METHODS: Final = (
    "Welch/t",
    "Seeded permutation",
    "Mann--Whitney ranks",
    "Bayesian posterior",
)


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


def _assert_fixture_backed_decision_claims(source: str) -> None:
    normalized = " ".join(source.split())
    assert "equality with the threshold is ``PASS``" in normalized
    assert "an anomaly remains ``INCONCLUSIVE``" in normalized


def _assert_comparative_boundaries(source: str) -> None:
    sections = {
        section.partition("\n")[0]: section
        for section in re.split(r"\n(?=[^\n]+\n-+\n)", source)[1:]
    }
    assert all(method in sections for method in _COMPARATIVE_METHODS)
    for method in _COMPARATIVE_METHODS:
        normalized = " ".join(sections[method].split())
        assert "does not determine perfcheck PASS/FAIL" in normalized
        assert "does not change product policy" in normalized
        assert (
            re.search(
                r"\b(determine|produce|yield)s? (a )?perfcheck (verdict|PASS/FAIL)",
                normalized.replace("does not determine perfcheck PASS/FAIL", ""),
                flags=re.IGNORECASE,
            )
            is None
        )
        assert all(
            term in normalized
            for term in ("Dataset:", "Question:", "Assumptions:", "Result:")
        )


def test_comparative_explanation_keeps_each_method_outside_product_policy() -> None:
    # Given: the linked explanation for canonical lesson 10.
    source = _read(Path("docs/explanation/comparative-methods.rst"))
    # When: each method's local artifact and policy boundary is checked.
    _assert_comparative_boundaries(source)
    # Then: the explanation links the actual runnable lesson and decisions chapter.
    assert "<../../examples/10-comparative-methods.py>" in source
    assert ":doc:`decisions-and-limitations`" in source


@pytest.mark.parametrize(
    "method",
    _COMPARATIVE_METHODS,
)
def test_comparative_contract_rejects_misleading_success_claim(method: str) -> None:
    # Given: the real explanation with one method claiming a product verdict.
    source = _read(Path("docs/explanation/comparative-methods.rst"))
    before, section = source.split(f"\n{method}\n", maxsplit=1)
    mutated = (
        before
        + f"\n{method}\n"
        + section.replace(
            "does not determine perfcheck PASS/FAIL",
            "does not determine perfcheck PASS/FAIL. It determines a perfcheck verdict",
            1,
        )
    )
    # When: the same contract checks this misleading-success fixture.
    # Then: it rejects the claim even if the other methods retain correct boundaries.
    with pytest.raises(AssertionError):
        _assert_comparative_boundaries(mutated)


@pytest.mark.parametrize(
    "method",
    [
        "Cohort bootstrap",
        "Welch or t-test",
        "F variance test",
        "Permutation test",
        "Mann--Whitney",
        "Bayesian framing",
    ],
)
def test_method_artifact_has_evidence_and_a_local_boundary(method: str) -> None:
    # Given: the method artifact table, excluding the earlier selection table.
    source = _read(Path("docs/explanation/decisions-and-limitations.rst"))
    table = source.split(".. list-table:: Method artifacts and boundaries")[1]

    # When: the reader inspects one method's row.
    row = next(row for row in table.split("   * - ") if row.startswith(method))
    columns = row.split("\n     - ")

    # Then: question/assumptions, linked evidence, interpretation and boundary coexist.
    assert len(columns) == 5
    assert "?" in columns[1]
    assert "<" in columns[2]
    assert columns[3].strip()
    assert (
        "Implemented." in columns[4]
        or "does not determine perfcheck PASS/FAIL" in columns[4]
    )


def test_decision_examples_link_exact_fixtures_and_preserve_verdicts() -> None:
    # Given: the explanation's fixture-backed threshold examples.
    source = _read(Path("docs/explanation/decisions-and-limitations.rst"))

    # When: a reader follows the equality and advisory claims.
    _assert_fixture_backed_decision_claims(source)

    # Then: concrete examples and downloadable evidence support those claims.
    for term in (
        "15 - 10 = 5",
        "20 - 15 = 5",
        "16 - 10 = 6",
        "20 - 14 = 6",
        "test_evaluate_regression_uses_a_strict_directional_cohort_bound",
        "test_evaluate_regression_keeps_directional_reference_anomalies_inconclusive",
        "test_bootstrap_cohorts_use_pcg64_draw_order_and_linear_quantiles",
        "<../../tests/test_bootstrap.py>",
        "<../../tests/test_policy_outcomes.py>",
        "<../../examples/08-bootstrap-and-decisions.py>",
        "0.05 / 2 = 0.025",
    ):
        assert term in source


@pytest.mark.parametrize(
    ("claim", "mutation"),
    [
        ("equality with the threshold is ``PASS``", "equality is ``FAIL``"),
        ("an anomaly remains ``INCONCLUSIVE``", "an anomaly yields ``FAIL``"),
    ],
)
def test_fixture_backed_claim_contract_rejects_wrong_verdicts(
    claim: str, mutation: str
) -> None:
    # Given: the actual explanation with one fixture-backed verdict reversed.
    source = _read(Path("docs/explanation/decisions-and-limitations.rst"))
    normalized = " ".join(source.split())
    assert claim in normalized
    mutated = normalized.replace(claim, mutation)

    # When: the same contract checks the misleading source.
    # Then: it rejects the reversed verdict, not merely a missing method name.
    with pytest.raises(AssertionError):
        _assert_fixture_backed_decision_claims(mutated)


def test_measurement_page_documents_supported_calculations_with_examples() -> None:
    # Given: the per-run measurement chapter read by a documentation user.
    measurement = _read(Path("docs/explanation/measurement-and-summaries.rst"))

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
    eligibility = _read(Path("docs/explanation/eligibility-and-comparability.rst"))

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
    comparison = _read(Path("docs/explanation/uncertainty-and-comparison.rst"))
    decisions = _read(Path("docs/explanation/decisions-and-limitations.rst"))

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


def test_decisions_page_contracts_method_selection_and_teaching_alternatives() -> None:
    # Given: the explanation distinguishing verdict evidence from teaching.
    decisions = _read(Path("docs/explanation/decisions-and-limitations.rst"))

    # When: its selection and alternative-method tables are inspected.

    # Then: only valid multi-run bootstrap evidence can decide PASS or FAIL.
    selection_terms = (
        "Valid multi-run cohort bootstrap",
        "Advisory single-current reference",
        "Incomparable or inadequate evidence after input validation",
        "Duplicate source identity or content",
        "``PASS`` or ``FAIL``",
        "``INCONCLUSIVE``",
        "``examples/08-bootstrap-and-decisions.py``",
        "``tests/test_bootstrap.py``",
        "``tests/test_policy_outcomes.py``",
    )
    alternative_methods = (
        "Cohort bootstrap",
        "Welch or t-test",
        "F variance test",
        "Permutation test",
        "Mann--Whitney",
        "Bayesian framing",
    )
    assert all(term in decisions for term in selection_terms)
    assert "validation before metric evaluation and report assembly" in " ".join(
        decisions.split()
    )
    assert all(method in decisions for method in alternative_methods)
    assert decisions.count("does not determine perfcheck PASS/FAIL") == 5


def test_classical_methods_remain_explicitly_unsupported() -> None:
    # Given: the comparison chapters and the classical contrast lesson.
    source = "\n".join(
        (
            _read(Path("docs/explanation/uncertainty-and-comparison.rst")),
            _read(Path("docs/explanation/decisions-and-limitations.rst")),
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
