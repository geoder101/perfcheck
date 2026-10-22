Plain-Python mechanics
======================

The arithmetic behind :doc:`measurement-and-summaries` and
:doc:`uncertainty-and-comparison` can be inspected without array syntax.
:download:`Lesson 09 <../../examples/09-plain-python-mechanics.py>` follows
lessons 06-08 with finite, deterministic toy inputs. Its helpers are educational,
not a production implementation, stable Python API, or source of verified
perfcheck evidence. The supported interface remains the CLI.

Location, spread, and slope
---------------------------

For values ``(4, 6, 10, 14, 20)``, the mean is ``10.8``. Accumulating with
``math.fsum`` avoids ordinary summation's unnecessary loss of precision.
Sample variance divides squared deviations by ``n - 1``, giving ``41.2``;
``math.sqrt`` gives sample SD approximately ``6.418723``. Dividing by ``n``
would instead compute population variance, a different statistic.

Linear quantiles sort the values and locate ``h = (n - 1) * q``. With
``j = floor(h)``, interpolate between the values at ``j`` and ``ceil(h)``
using weight ``h - j``. Endpoints select the minimum and maximum; a singleton
selects its only value. Here q90 is ``17.6``, not the nearest observed value.
This is NumPy's explicit ``method="linear"`` convention, not a nearest-rank rule.

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

Advisory reference quantile
---------------------------

For one current throughput value ``20``, orientation gives ``-20``. The baseline
upper-tail linear quantile at ``1 - 0.025`` is ``-25.25``, giving reference effect
``5.25``. It exceeds threshold ``5`` strictly and flags an anomaly. As in
``bootstrap_reference.py``, this is advisory only: the result remains
INCONCLUSIVE, has no bootstrap confidence interval, and cannot yield PASS/FAIL.
Equality with the threshold would not flag an anomaly.

Lesson 09 does not implement artifact persistence, hashes, integrity checking,
eligibility gates, or policy evaluation. Use the CLI workflow in
:doc:`../tutorials/first-comparison` to produce verified evidence. The executable
checks in :download:`the mechanics tests <../../tests/test_examples_mechanics.py>`
lock the numeric examples and repeatable isolated output; run them with
``just examples-check``.
