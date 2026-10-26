Decisions and limitations
=========================

This chapter explains the verdict contract and its boundaries. A perfcheck
verdict is a reproducible policy result over validated artifacts, not a broad
scientific conclusion about a service or its users.

Read :doc:`probability-and-distributions` and :doc:`experimental-design` first
for the sampling model and independent experimental unit. Then read
:doc:`inference-and-power` for the distinction between effect size, uncertainty,
test error and power. Those concepts explain the limits of a decision; they
don't add a p-value engine to perfcheck.

Metric verdicts
---------------

For cohort-bootstrap evidence, perfcheck compares the lower decision bound
with the metric's nonnegative practical threshold :math:`T`:

.. math::

   \mathrm{FAIL}\quad\text{if and only if}\quad
   L_{\mathrm{decision}} > T.

All other cohort-bootstrap cases pass. In particular, equality passes:
:math:`L_{\mathrm{decision}} = T` produces ``PASS``, not ``FAIL``. The strict
comparison prevents a value exactly on the configured boundary from being
classified as a regression.

This rule separates an observed effect from the policy's evidence requirement.
A higher-is-worse latency increase from baseline 80 ms to current 90 ms has an
observed effect of +10 ms, but that number alone doesn't decide whether the
lower bootstrap bound exceeds, for example, :math:`T=5` ms. A noisy cohort may
have an observed effect above 5 and a lower bound below 5. That still passes the
implemented rule. ``PASS`` means no strict bound breach, not "the true increase
is below 5" or "the two versions are equivalent".

Conversely, a sufficiently concentrated bound can exceed a small threshold for
an operationally unimportant effect if the policy was chosen poorly. Choose
the threshold in metric units from operational costs before inspecting the
data, not from whichever value produces a desired verdict. Orientation doesn't
normalize units: a 5 ms latency margin and a 5 requests/s throughput margin are
different policies.

An enabled metric is ``INCONCLUSIVE`` when comparison cannot select a valid
method, including an incompatible policy hash or metric fingerprint,
overlapping source intervals, insufficient eligible
current or baseline runs, or an incompatible requested mode. A disabled metric
is also recorded as ``INCONCLUSIVE`` and does not act as a gate. The report
retains exclusions and exact reasons, so an inconclusive result is not silently
converted to a pass.

Distinguish a reportable inconclusive outcome from rejected input. In the CLI
workflow, duplicated source run IDs or source content hashes fail cohort
validation before metric evaluation and report assembly. They don't produce an
inconclusive metric report. Artifact validation errors must be resolved at the
input boundary, not interpreted as statistical evidence.

The baseline-reference method is different by design. Its anomaly flag does
not produce ``FAIL`` or ``PASS``. It is advisory evidence and the metric verdict
remains ``INCONCLUSIVE``. See :doc:`uncertainty-and-comparison` for its
upper-tail quantile calculation.

Method selection in practice
----------------------------

The following table separates the policy paths from inadequate evidence. It
applies the same orientation for every metric, so a positive oriented effect
always means worse in the policy direction. It also applies the fixed
Bonferroni allocation across enabled gates before method selection.

.. list-table:: Decision paths
   :header-rows: 1
   :widths: 24 28 48

   * - Evidence state
     - Policy selection and evidence
     - Verdict consequence
   * - Valid multi-run cohort bootstrap
     - Eligible, comparable current and baseline cohorts meet the configured
       minima. The seeded PCG64 percentile calculation compares its oriented
       lower bound strictly with the practical threshold.
     - This is the only path that can yield ``PASS`` or ``FAIL``. Equality with
       the threshold is ``PASS``. The fixed cohort fixture in
       ``tests/test_bootstrap.py`` and the directional equality cases in
       ``tests/test_policy_outcomes.py`` are deterministic examples. Run
       ``examples/08-bootstrap-and-decisions.py`` for the corresponding
       teaching demonstration.
   * - Advisory single-current reference
     - Exactly one eligible, comparable current run and enough baseline runs
       select the upper-tail oriented baseline reference. A strict anomaly can
       be recorded.
     - The result is ``INCONCLUSIVE`` even when the anomaly is true. The
       reference fixture in ``tests/test_bootstrap.py`` and the anomaly cases
       in ``tests/test_policy_outcomes.py`` show this rule.
   * - Incomparable or inadequate evidence after input validation
     - Exclusions leave too few eligible runs, or policy hash, fingerprint,
       interval, or requested mode is incompatible.
       No method is selected.
     - The result is ``INCONCLUSIVE`` with the retained reason and exclusions.
       It is not a pass inferred from missing evidence.
   * - Duplicate source identity or content
     - Cohort input validation rejects repeated source run IDs or source content
       hashes, including duplicates across current and baseline.
     - The CLI stops before metric evaluation and report assembly; this isn't a
       reportable ``INCONCLUSIVE`` result.

Eligibility and comparability are gates, not statistical diagnostics. They make
the retained artifacts traceable and consistently configured, but they do not
establish IID sampling, independence, representativeness, normality, or a
causal comparison. A disabled metric contributes neither a gate nor a
Bonferroni denominator and remains ``INCONCLUSIVE``.

In ``auto`` mode, exactly one eligible current run selects reference mode;
otherwise perfcheck attempts cohort bootstrap. An explicit mode still has to
meet its own count requirements. Switching modes cannot repair incomparable
artifacts. See :doc:`eligibility-and-comparability` for the upstream gates.

The allocation is :math:`\alpha_{\mathrm{effective}} =
\alpha_{\mathrm{nominal}} / m`, where :math:`m` counts every enabled policy
metric, not just metrics with usable evidence. For example,
:math:`0.05 / 2 = 0.025` even if one enabled metric becomes inconclusive.
Filtering evidence does not redistribute its allocation to another metric.
This is a nominal Bonferroni-style allocation. As derived in
:doc:`multiple-testing`, a family-wise error guarantee additionally needs valid
individual error control. The approximate percentile bootstrap hasn't thereby
been demonstrated to meet that premise for the workload. Neither run-count
minima nor an increased resample count establish nominal coverage.

Fixture-backed boundary examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The downloadable :download:`policy outcome fixtures
<../../tests/test_policy_outcomes.py>` include
``test_evaluate_regression_uses_a_strict_directional_cohort_bound``.
Each case has five constant current values and ten constant baseline values,
so every resampled mean difference equals the oriented effect. With
:math:`T=5`, equality with the threshold is ``PASS``:

* Higher-is-worse: current 15, baseline 10 gives :math:`15 - 10 = 5`, so
  the lower bound is 5 and the result is ``PASS``. Current 16 instead gives
  :math:`16 - 10 = 6`, which is ``FAIL``.
* Lower-is-worse: negate values before subtracting means. Current 15,
  baseline 20 gives :math:`20 - 15 = 5`, which is ``PASS``. Current 14
  instead gives :math:`20 - 14 = 6`, which is ``FAIL``.

In the same file,
``test_evaluate_regression_keeps_directional_reference_anomalies_inconclusive``
uses one current run and ten constant baseline values. Its oriented reference
effect is 6 against :math:`T=5`: an anomaly remains ``INCONCLUSIVE`` in both
directions. The adjacent reference-equality fixture records no anomaly at 5,
but still returns ``INCONCLUSIVE``, not ``PASS``.

For the arithmetic behind the reference tail, :download:`bootstrap fixtures
<../../tests/test_bootstrap.py>` include
``test_baseline_reference_uses_the_oriented_tail_quantile_as_an_advisory``:
current throughput 20 and baseline values 30, 25, 35 produce an oriented
reference quantile of -25.25 and effect of 5.25. The anomaly is true; it is
not a regression verdict. :download:`Lesson 08
<../../examples/08-bootstrap-and-decisions.py>` is the runnable teaching
contrast, not a replacement for CLI method selection.

Suite aggregation
-----------------

Only enabled metric outcomes enter suite aggregation. The reduction begins at
``PASS`` and follows these precedence rules:

* Any enabled ``FAIL`` makes the suite ``FAIL`` immediately.
* Otherwise, any enabled ``INCONCLUSIVE`` makes the suite ``INCONCLUSIVE``.
* The suite is ``PASS`` only when every enabled metric passes.

Consequently, a single advised baseline-reference metric can leave a suite
inconclusive unless another enabled metric has already failed. Disabled metrics
cannot change the suite status.

For example, enabled outcomes ``PASS, INCONCLUSIVE`` reduce to ``INCONCLUSIVE``;
``FAIL, INCONCLUSIVE`` reduce to ``FAIL``. A disabled inconclusive metric cannot
turn an otherwise passing suite inconclusive. Failure takes precedence because
an already-detected policy breach isn't erased by missing evidence elsewhere.
The ordering is an operational contract, not a probability calculation or a
claim that the uncertain metric is safe.

Method alternatives are teaching material, not decision engines
---------------------------------------------------------------

The methods below answer different questions. Their entries identify either a
deterministic perfcheck fixture or a cited source, rather than presenting an
unsupported computation as product evidence. The runnable contrast in
``examples/08-bootstrap-and-decisions.py`` shows the oriented bootstrap rule and
a Welch statistic without calculating a p-value.

:doc:`comparative-methods` and :download:`Lesson 10
<../../examples/10-comparative-methods.py>` compute deterministic educational
Welch/t, seeded permutation, tied-rank and Bayesian contrasts. Each has its own
dataset, question, assumptions, result and explicit non-verdict boundary.

.. list-table:: Method artifacts and boundaries
   :header-rows: 1
   :widths: 16 23 24 20 17

   * - Method
     - Question and assumptions
     - Deterministic fixture or cited evidence
     - Interpretation
     - Perfcheck boundary
   * - Cohort bootstrap
     - Is the oriented lower percentile bound strictly above the practical
       threshold for eligible, comparable multi-run cohorts? It resamples the
       observed cohort values with replacement and does not validate IID,
       normality, causal similarity, or representativeness.
     - :download:`Bootstrap fixtures <../../tests/test_bootstrap.py>` include
       ``test_bootstrap_cohorts_use_pcg64_draw_order_and_linear_quantiles``.
       Seed 19, effective alpha 0.025 and 4000 draws give observed effect
       1.1357142857142852 and lower bound -3.9287500000000004. The same
       mechanics are visible in ``examples/08-bootstrap-and-decisions.py``.
     - The lower decision bound is approximate percentile-bootstrap policy
       evidence, not a p-value or an interval with demonstrated nominal
       coverage. Its strict threshold rule yields the documented verdict.
     - Implemented. It determines perfcheck ``PASS`` or ``FAIL`` only after
       valid multi-run method selection.
   * - Welch or t-test
     - Do two sample means differ under a specified null model? Welch's
       formulation permits unequal variances and uses an approximate degrees of
       freedom. Independent samples and an appropriate normal approximation
       are needed for its usual tail interpretation. A pooled t-test adds an
       equal-variance assumption; paired designs are distinct.
     - `NIST's two-sample t-test reference
       <https://www.itl.nist.gov/div898/handbook/eda/section3/eda353.htm>`_
       gives the statistic and Welch--Satterthwaite degrees of freedom.
     - A t statistic or a model-based tail calculation would concern the chosen
       null model, not the configured practical threshold policy.
     - It does not determine perfcheck PASS/FAIL.
   * - F variance test
     - Does a variance ratio support a specified equal-variance null? A p-value
       is a tail probability under a stated model and selected tail. The usual
       F variance test assumes independent normal samples and is sensitive to
       nonnormality; it is not a general test of mean regression.
     - `NIST's F-test reference
       <https://www.itl.nist.gov/div898/handbook/eda/section3/eda359.htm>`_
       defines the variance ratio and its critical regions.
     - A variance comparison or tail probability is not a practical-effect
       threshold decision. A p-value is not the probability that the null is
       true, nor is a large p-value proof of equivalence.
     - It does not determine perfcheck PASS/FAIL.
   * - Permutation test
     - Is a chosen statistic unusual under label relabeling? The randomization
       or exchangeability justification must match the data-generating design.
     - `Millman, Ottoboni, and Stark's permutation text
       <https://statlab.github.io/permute/permute.pdf>`_ describes the
       exchangeability condition and simulated relabeling distribution.
     - Its null distribution concerns the chosen statistic and relabeling
       model, not perfcheck's seeded percentile rule.
     - It does not determine perfcheck PASS/FAIL.
   * - Mann--Whitney
     - Do two independent samples show a rank-based location or distributional
       contrast? Its interpretation depends on the target hypothesis, ties, and
       the assumptions attached to the chosen version.
     - `Johns Hopkins lecture notes on the Mann/Whitney test
       <https://biostat.jhsph.edu/~iruczins/teaching/140.652/lecture26.pdf>`_
       describe rank sums, independent errors, and the normality distinction.
     - A rank statistic is a contrast of ordered observations, not an oriented
       practical-threshold breach. It is not automatically a test of medians;
       a location-shift interpretation needs additional distributional
       assumptions.
     - It does not determine perfcheck PASS/FAIL.
   * - Bayesian framing
     - How do a stated likelihood and prior combine into a posterior for a
       specified parameter? The model and prior are part of the conclusion.
     - `Stan's Bayesian inference reference
       <https://mc-stan.org/docs/stan-users-guide/how-stan-works.html>`_
       explains posterior inference from a likelihood and prior.
     - A posterior summary is conditional on its model and prior; it is not the
       policy's bootstrap lower bound. A posterior probability needs that
       explicit model, not a relabeling of a bootstrap percentile.
     - It does not determine perfcheck PASS/FAIL.

**perfcheck does not implement t-tests, Welch tests, F-tests, or p-values.**
It also does not implement permutation tests, Mann--Whitney tests, or Bayesian
inference. It does not calculate a t statistic, a Welch degrees of freedom, an
F statistic, a p-value, a permutation distribution, a rank statistic, or a
posterior. These concepts appear here only to prevent a familiar term from being
read into the implemented bootstrap and threshold policy.

Interpretation boundaries
-------------------------

The comparison needs enough eligible runs under one matching policy, but it
does not diagnose dependence caused by cache state, traffic, deployments,
retries, or shared infrastructure. It does not verify normality, test an IID
assumption, estimate a causal effect, or validate that a convenience cohort
represents production. A larger cohort can reduce some sampling variability
without curing systematic bias or a changed workload.

Thresholds express a policy choice about practical size. They are not derived
from a p-value, a confidence level, or a universal error budget. Read a pass as
the absence of a bootstrap-bound threshold breach under this policy and these
artifacts. Read a failure as an observed policy breach that merits investigation.
Neither result proves that every future deployment will have the same outcome.

Investigating a result without changing its meaning
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A failure calls for inspecting the effect units, practical threshold, lower
decision bound, diagnostic spread, cohort counts, exclusions and source runs.
Then ask whether workload mix, environment drift or shared infrastructure could
explain the difference. Hashes and fingerprints establish what was compared;
they don't identify why a difference occurred. A new experiment with randomized
or blocked allocation may be needed for a causal claim.

A pass with a wide bootstrap spread is different evidence from a pass with a
narrow spread. Nevertheless both have the same product status when the strict
bound rule doesn't breach. Don't substitute a subjective reading of the
diagnostic 0.025/0.975 bounds for the effective-alpha decision bound. Nor should
an inconclusive result be "fixed" by dropping an enabled metric, repeatedly
changing the baseline, or trying seeds until it passes. These choices change
the experiment or policy and can introduce selection bias.

The alpha allocation concerns the enabled gates in one configured comparison.
It doesn't automatically cover repeated releases, interim looks, undocumented
subgroup searches or repeated comparisons against a reused baseline. A seed
makes a calculation repeatable, not independent of previous calculations.
See :doc:`multiple-testing` for family definition and stopping, and
:doc:`uncertainty-and-comparison` for finite-sample and resampling limitations.

Continue with :download:`Lab 08 <../../examples/08-bootstrap-and-decisions.py>`
to exercise the rule and :doc:`plain-python-mechanics` to check its arithmetic.
:download:`Lab 10 <../../examples/10-comparative-methods.py>` and
:doc:`comparative-methods` then show why a null-tail probability, a rank contrast
or a Bayesian posterior cannot silently replace that rule.
