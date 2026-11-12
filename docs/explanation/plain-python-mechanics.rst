Plain-Python mechanics
======================

The arithmetic behind :doc:`measurement-and-summaries` and
:doc:`uncertainty-and-comparison` can be inspected without array syntax.
`Lesson 09 <https://github.com/geoder101/perfcheck/blob/main/examples/09-plain-python-mechanics.py>`_ follows
lessons 06-08 with finite, deterministic toy inputs. Its helpers are educational,
not a production implementation, stable Python API, or source of verified
perfcheck evidence. The supported interface remains the CLI.

Prerequisites are :doc:`probability-and-distributions` and
:doc:`measurement-and-summaries`; :doc:`experimental-design` explains why a
scalar run summary isn't automatically an independent replicate. Work through
`Lab 08 <https://github.com/geoder101/perfcheck/blob/main/examples/08-bootstrap-and-decisions.py>`_ first to know
what the arithmetic is intended to describe.

Location, spread, and slope
---------------------------

For values ``(4, 6, 10, 14, 20)``, the mean is ``10.8``. Accumulating with
``math.fsum`` avoids ordinary summation's unnecessary loss of precision.
Sample variance divides squared deviations by ``n - 1``, giving ``41.2``;
``math.sqrt`` gives sample SD approximately ``6.418723``. Dividing by ``n``
would instead compute population variance, a different statistic.

Written out, the calculations are

.. math::

   \overline x&=\frac{4+6+10+14+20}{5}=10.8,\\
   \sum_i(x_i-\overline x)^2&=46.24+23.04+0.64+10.24+84.64=164.8,\\
   s^2&=164.8/(5-1)=41.2.

For IID observations with finite variance, estimating the mean consumes one
degree of freedom: :math:`\sum_i(X_i-\overline X)=0`. In expectation,
:math:`\operatorname{E}\sum_i(X_i-\overline X)^2=(n-1)\sigma^2`, which
explains the variance correction. It doesn't make the sample SD itself unbiased
or cure dependence. The SD describes spread of observations; an estimated SE
of an IID sample mean is :math:`s/\sqrt n`, a different quantity.

Linear quantiles sort the values and locate ``h = (n - 1) * q``. With
``j = floor(h)``, interpolate between the values at ``j`` and ``ceil(h)``
using weight ``h - j``. Endpoints select the minimum and maximum; a singleton
selects its only value. Here q90 is ``17.6``, not the nearest observed value.
This is NumPy's explicit ``method="linear"`` convention, not a nearest-rank rule.

For q90 specifically, :math:`h=4(0.9)=3.6`, so the weight on the fifth value
is 0.6 and the result is :math:`14+0.6(20-14)=17.6`. Interpolation can return
an unobserved value without implying that such an observation occurred.

Least-squares slope is the sum of centered time/value cross-products divided
by the sum of centered squared times. At elapsed seconds
``(0, 15, 30, 45, 60)``, the slope is ``0.266666...`` value units per second.
Subtracting the first retained timestamp gives the production time coordinate;
shifting all times by a constant does not change this centered slope.

These formulas mirror ``summary_statistics.py``: mean uses ``math.fsum``, SD
uses Bessel's correction, and slope is centered least squares. Tests compare
the toy results against NumPy mean, linear quantiles, ``var/std(ddof=1)``, and
centered least squares with numerical tolerances. This is formula agreement
on representative inputs, not bitwise equality for every floating-point input.
The helpers reject empty/nonfinite inputs, undefined sample variance, and
degenerate slope inputs. Finite inputs can still overflow intermediate
arithmetic; these small examples are not a general numerical library.

Orientation, resampling, and bounds
-----------------------------------

Higher-is-worse values retain their sign. Lower-is-worse values are negated,
so a positive current-minus-baseline mean always means worsening. For baseline
throughput ``(30, 25, 35)`` and current ``(20, 22, 24)``, oriented means differ
by ``8``. Resampling draws each cohort's original number of observations with
replacement, computes its mean, and subtracts baseline from current.

The baseline mean is 30 and current mean 22, so after negation the difference
is :math:`-22-(-30)=8` throughput units of worsening. For ordinary latency,
keep the signs: baseline 80 ms and current 90 ms give :math:`90-80=10` ms.
Don't reverse either the subtraction order or the direction a second time.

One possible resample of the oriented current cohort ``(-20, -22, -24)`` is
``(-20, -20, -24)``; one baseline resample is ``(-30, -25, -25)``. Their means
are :math:`-64/3` and :math:`-80/3`, giving a replicate difference
:math:`16/3`. Replacement permits duplicates and omissions. Keep cohort sizes
fixed and compute many such differences; don't pool the groups and shuffle
their labels, which would answer the permutation question in
:doc:`comparative-methods` instead.

The lesson uses ``random.Random`` with seeds 42 and 43 and 32 draws per cohort.
These bootstrap draws are educational and neither bitwise nor evidence-compatible
with production NumPy PCG64. Production uses one fresh PCG64 stream per metric,
draws current then baseline within each replicate, uses NumPy float64 means,
and enforces at least ``2000 * enabled_metric_count`` resamples. The lesson's
separate streams and tiny draw count intentionally do not reproduce that contract.
No new RNG, replacement for NumPy, or alternate product decision path is proposed.

On an identical fixed sequence of differences, both implementations select
linear quantiles: effective alpha for the lower decision bound, and 0.025/0.975
for the diagnostic bounds. Here ``0.05 / 2 = 0.025`` illustrates fixed Bonferroni
allocation, so the lower decision and diagnostic probabilities coincide; they
need not coincide with another enabled-metric count. Diagnostic bounds are not
p-values. A deterministic toy bound does not establish eligibility, comparable
runs, independent observations, or a perfcheck PASS/FAIL verdict. See
:doc:`decisions-and-limitations` for the actual strict-threshold policy.

For a hand-checkable illustration, suppose a sorted toy sequence of differences
is ``(-2, 0, 1, 4, 7)``. At :math:`q=0.025`, :math:`h=4q=0.1`, so the lower
quantile is :math:`-2+0.1(0-(-2))=-1.8`. At :math:`q=0.975`, it is
:math:`4+0.9(7-4)=6.7`. With one enabled gate the decision quantile instead
uses 0.05 and gives -1.6. A diagnostic interval spanning zero is descriptive
spread, not a proof of no effect; a lower decision bound below the practical
threshold doesn't establish equivalence. The confidence/test relationship in
:doc:`inference-and-power` needs matching procedures and validated assumptions.

Advisory reference quantile
---------------------------

For one current throughput value ``20``, orientation gives ``-20``. The baseline
upper-tail linear quantile at ``1 - 0.025`` is ``-25.25``, giving reference effect
``5.25``. It exceeds threshold ``5`` strictly and flags an anomaly. As in
``bootstrap_reference.py``, this is advisory only: the result remains
INCONCLUSIVE, has no bootstrap confidence interval, and cannot yield PASS/FAIL.
Equality with the threshold would not flag an anomaly.

To verify the reference arithmetic, sort the oriented baseline as
``(-35, -30, -25)``. At :math:`q=0.975`, :math:`h=2q=1.95`, so interpolate
:math:`-30+0.95(-25-(-30))=-25.25`. The reference difference is then
:math:`-20-(-25.25)=5.25`. Taking the upper quantile before negating would use
the wrong throughput tail: orientation precedes quantile selection.

Lesson 09 does not implement artifact persistence, hashes, integrity checking,
eligibility gates, or policy evaluation. Use the CLI workflow in
:doc:`../tutorials/first-comparison` to produce verified evidence. The executable
checks in `the mechanics tests <https://github.com/geoder101/perfcheck/blob/main/tests/test_examples_mechanics.py>`_
lock the numeric examples and repeatable isolated output; run them with
``just examples-check``.

Next, :doc:`multiple-testing` derives the allocation that selects the decision
quantile. `Lab 10 <https://github.com/geoder101/perfcheck/blob/main/examples/10-comparative-methods.py>`_ and
:doc:`comparative-methods` distinguish bootstrap resampling from a null-tail
test and a posterior update. Arithmetic agreement is necessary for reliable
implementation; the sampling design and calibration are separate obligations.
