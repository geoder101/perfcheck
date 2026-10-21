Decisions and limitations
=========================

This chapter explains the verdict contract and its boundaries. A perfcheck
verdict is a reproducible policy result over validated artifacts, not a broad
scientific conclusion about a service or its users.

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

An enabled metric is ``INCONCLUSIVE`` when comparison cannot select a valid
method, including an incompatible policy hash or metric fingerprint, duplicated
source identity or content, overlapping source intervals, insufficient eligible
current or baseline runs, or an incompatible requested mode. A disabled metric
is also recorded as ``INCONCLUSIVE`` and does not act as a gate. The report
retains exclusions and exact reasons, so an inconclusive result is not silently
converted to a pass.

The baseline-reference method is different by design. Its anomaly flag does
not produce ``FAIL`` or ``PASS``. It is advisory evidence and the metric verdict
remains ``INCONCLUSIVE``. See :doc:`uncertainty-and-comparison` for its
upper-tail quantile calculation.

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

Classical methods are contrasts, not perfcheck operations
----------------------------------------------------------

Classical hypothesis testing often begins with a null hypothesis, an alternative
hypothesis, a test statistic, and assumptions used to approximate a reference
distribution. A p-value is a tail probability calculated within that specified
model. It is not the probability that a regression hypothesis is true, and it
does not measure practical importance. One-sided and two-sided tests choose
different tails before looking at the data.

A one-sample or paired t-test is commonly associated with a Student t
reference distribution. Welch's two-sample t-test is a separate method that
allows unequal variances through a degrees-of-freedom approximation. An F
statistic appears in variance-ratio tests and analysis-of-variance settings.
Normality and CLT arguments can support some classical approximations under
their conditions. Sampling error describes variation caused by observing a
finite sample rather than an entire population.

**perfcheck does not implement t-tests, Welch tests, F-tests, or p-values.**
It does not calculate a t statistic, a Welch degrees of freedom, an F statistic,
or a p-value, and none of those quantities determine a perfcheck verdict.
Classical methods appear here only to prevent a familiar term from being read
into the implemented bootstrap and threshold policy.

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
