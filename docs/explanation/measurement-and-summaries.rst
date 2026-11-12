Per-run measurement and summaries
=================================

Each raw run contains timestamped observations for a metric over its source
interval. ``summarize`` first applies the eligibility rules described in
:doc:`eligibility-and-comparability`; it then reduces the retained observations
to one finite scalar selected by the metric policy. That scalar is evidence for
one run, not an estimate that automatically applies to a wider population. See
:doc:`statistical-foundations` for that distinction.

Let the retained observations, ordered by timestamp, be
:math:`(t_1, x_1), \ldots, (t_n, x_n)`. Calculations use the ordered values
:math:`x_1, \ldots, x_n`. Floating-point sums use ``math.fsum`` rather than a
naive left-to-right sum, reducing rounding error when magnitudes differ. It
does not make finite-precision arithmetic exact or rescue a non-finite input.

Choose the question before the statistic
---------------------------------------------

A summary deliberately discards information. A mean describes average level;
a tail quantile describes a high position; an endpoint difference describes
net movement. Choose the statistic because it answers the operational
question, not because it happens to produce a favorable comparison.

For instance, ``(10, 10, 10, 50)`` ms and ``(20, 20, 20, 20)`` ms both have
mean 20 ms. The first includes a high tail, while the second doesn't. The
same mean therefore needn't imply the same experience. Conversely, the p95
of these four observations relies heavily on very little tail evidence.
No choice recovers events the measurement process never observed.

The mean here weights retained *observations* equally. An irregular time
series isn't automatically a time-weighted average. Nor is a p95 of scraped
values necessarily a p95 of individual request latencies: that depends on
what the query returns. Preserve the metric's unit and meaning through the
whole workflow. See :doc:`experimental-design` for why the choice of
experimental unit matters.

Location and tails
------------------

``mean``
   The arithmetic mean is

   .. math::

      \bar{x} = \frac{\operatorname{fsum}(x_1, \ldots, x_n)}{n}.

   It measures average level within the retained window. Interpreting it as an
   expected value assumes the run's observations are relevant to the intended
   operating condition. Bursts or a multimodal workload can make one average
   hide important behavior.

   Worked example: for :math:`(2, 4, 6, 8)`, ``fsum`` is 20, so
   :math:`\mathrm{mean} = 20 / 4 = 5`.

``p50``, ``p90``, ``p95``, and ``p99``
   These are quantiles at :math:`p = 0.50, 0.90, 0.95, 0.99`, respectively,
   using NumPy's ``linear`` method. For sorted values
   :math:`y_0 \leq \cdots \leq y_{n-1}`, set :math:`h = (n - 1)p`,
   :math:`k = \lfloor h \rfloor`, and :math:`g = h-k`. The result is

   .. math::

      (1-g)y_k + gy_{\min(k+1, n-1)}.

   Read the symbols as a recipe:

   * :math:`y_i` is the observation at zero-based position :math:`i` after
     sorting by value, not timestamp; :math:`n` is the retained observation count.
   * :math:`p` is the quantile probability between 0 and 1, so P90 uses 0.90,
     not 90. The fractional zero-based rank :math:`h=(n-1)p` locates it between
     the first position, 0, and the last position, :math:`n-1`.
   * :math:`k=\lfloor h\rfloor` rounds that rank down to the lower neighbor's
     index. The fractional part :math:`g=h-k` is the weight on the upper
     neighbor; :math:`1-g` is the weight on the lower neighbor.

   Thus :math:`(1-g)y_k` is the lower neighbor's contribution and
   :math:`g y_{\min(k+1,n-1)}` is the upper neighbor's contribution. Their
   weights sum to one. The minimum in the upper index keeps it within the
   observed array at the final position; it doesn't select the smaller value.

   A tail quantile describes a position in this run's retained values, not a
   service-level guarantee. Sparse samples, a short window, or a workload that
   misses rare events can make P90, P95, and especially P99 misleading.

   Worked example: for sorted values :math:`(2, 4, 6, 8)`, P50 has
   :math:`h=1.5` and is :math:`5`; P90 has :math:`h=2.7` and is
   :math:`0.3(6)+0.7(8)=7.4`. The same linear rule gives P95 = 7.7 and
   P99 = 7.94.

   For P50 in that example, :math:`n=4`, :math:`p=0.5`, :math:`h=1.5`,
   :math:`k=1`, and :math:`g=0.5`. The neighbors are :math:`y_1=4` and
   :math:`y_2=6`, so the contributions are :math:`0.5(4)=2` and
   :math:`0.5(6)=3`, totaling 5. At :math:`p=0`, the rule returns :math:`y_0=2`;
   at :math:`p=1`, it returns :math:`y_3=8`, with :math:`g=0` in both cases.
   An integer rank likewise returns that observation without blending. For a
   single retained observation, both neighbors are the same value for every
   probability.

   A finite-sample interpolated P95 needn't have exactly 95% of observed values
   below it. In this four-point example, only three of four values are below
   7.7. The interpolation convention provides a reproducible estimate, not
   an exact statement about empirical ranks. A p95 is also unrelated to a
   test's p-value; see :doc:`probability-and-distributions`.

Extremes and spread
-------------------

``min`` and ``max``
   These are :math:`\min_i x_i` and :math:`\max_i x_i`. They identify the
   observed extremes in the retained window. A single measurement anomaly can
   dominate either result, and no observed extreme bounds future values.

   Worked example: for :math:`(2, 4, 6, 8)`, min = 2 and max = 8.

``std``
   This is the sample standard deviation with Bessel correction:

   .. math::

      s = \sqrt{\frac{\operatorname{fsum}((x_i-\bar{x})^2)}{n-1}}.

   The correction uses :math:`n-1`, so the statistic requires at least two
   retained points. It describes within-run spread. It is not a confidence
   interval, and time dependence or changing workload can make a single spread
   value a poor summary of stability.

   Worked example: for :math:`(3, 5, 7)`, :math:`\bar{x}=5` and the squared
   deviations sum to :math:`4+0+4=8`; thus ``std`` =
   :math:`\sqrt{8/(3-1)}=2`.

Why divide by n minus one? (optional mathematics)
------------------------------------------------------

Estimating the center from the same sample pulls the squared deviations
downward. Once :math:`\bar{x}` is fixed, the deviations must sum to zero,
so only :math:`n-1` are free to vary. Under IID sampling with finite variance
:math:`\sigma^2`, the identity

.. math::

   \sum_i(X_i-\bar{X})^2
   =\sum_i(X_i-\mu)^2-n(\bar{X}-\mu)^2

gives expectation :math:`n\sigma^2-n(\sigma^2/n)=(n-1)\sigma^2`.
Dividing by :math:`n-1` therefore makes :math:`s^2` unbiased for the population
variance under those assumptions. Dividing by :math:`n` would have expectation
:math:`(n-1)\sigma^2/n` instead.

The square root :math:`s` isn't itself generally an unbiased estimator of
:math:`\sigma`. More importantly, the IID derivation doesn't establish IID
sampling for a time series. Perfcheck computes the corrected sample spread
as a descriptive statistic; it doesn't certify the sampling assumptions
needed for that unbiasedness interpretation.

Standard deviation isn't standard error
--------------------------------------------

Standard deviation describes spread among observations. Standard error (SE)
is the standard deviation of an estimator's sampling distribution. For an
average of independent, identically distributed values with variance
:math:`\sigma^2`,

.. math::

   \operatorname{Var}(\bar{X})
   =\operatorname{Var}\left(\frac{1}{n}\sum_i X_i\right)
   =\frac{1}{n^2}\sum_i\operatorname{Var}(X_i)
   =\frac{\sigma^2}{n},
   \qquad \operatorname{SE}(\bar{X})=\frac{\sigma}{\sqrt{n}}.

We usually don't know :math:`\sigma`, so :math:`s/\sqrt{n}` estimates the
SE under this model. For ``(3, 5, 7)`` ms, the sample SD is 2 ms and the
estimated SE of the mean is :math:`2/\sqrt{3}\approx1.155` ms. These are
different quantities calculated from the same values. Quadrupling the number
of independent observations halves the model's SE; it doesn't halve the
underlying population SD.

This calculation is educational, not an extra perfcheck output. If the inputs
are run summaries, :math:`n` counts independent runs. If the inputs are
within-run scrapes, using their count as independent repetitions needs a
separate justification. Perfcheck's ``std`` describes within-run values;
it isn't the standard error of the between-run comparison.

Optional mathematics: dependence and finite populations
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Without independence, the full variance calculation includes covariances:

.. math::

   \operatorname{Var}(\bar{X})=
   \frac{1}{n^2}\left(\sum_i\operatorname{Var}(X_i)
   +2\sum_{i<j}\operatorname{Cov}(X_i,X_j)\right).

Positive covariance, common in nearby time measurements, can make the
independence-based SE too small. Scraping twice as fast doesn't necessarily
create twice the information. It can simply observe the same state more often.

A different dependence arises when taking a simple random sample *without
replacement* from a fixed finite population of size :math:`N`. Define
:math:`\sigma_N^2=N^{-1}\sum_{j=1}^N(x_j-\mu_N)^2`. Then

.. math::

   \operatorname{SE}(\bar{X})=
   \frac{\sigma_N}{\sqrt{n}}\sqrt{\frac{N-n}{N-1}}.

The final square root is the finite-population correction with this definition
of population variance. Using sample variance with denominator :math:`n-1`
instead gives the estimated SE :math:`(s/\sqrt{n})\sqrt{1-n/N}`.
For :math:`N=100`, :math:`n=25`, and :math:`\sigma_N=10` ms, the model SE is
:math:`2\sqrt{75/99}\approx1.741` ms rather than 2 ms. At a census
:math:`n=N`, uncertainty about this fixed finite-population mean is zero,
not uncertainty about future changing conditions.

These formulas require genuine simple random sampling without replacement.
A benchmark's hypothetical future runs aren't a fixed list of 100 objects,
and a long scrape window isn't a census of all future service behavior.
Perfcheck doesn't apply a finite-population correction.

Ordered and trend summaries
---------------------------

``first``
   The value :math:`x_1` at the earliest retained timestamp. It represents the
   beginning of the analyzed window, not necessarily a cold-start value because
   warmup trimming may have removed earlier observations.

   Use it to check the starting memory footprint or queue depth after a fixed
   warmup. One unusual endpoint can dominate it, so align window boundaries
   across runs rather than treating it as a typical level.

``last``
   The value :math:`x_n` at the latest retained timestamp. It represents the
   end of the analyzed window, not a forecast or a guarantee of steady state.

   Use it to inspect memory remaining after a fixed-duration workload or the
   queue backlog at shutdown. A transient final scrape can dominate the result;
   a low last value doesn't show that the rest of the run was healthy.

``delta``
   The endpoint difference :math:`x_n - x_1`. It reports net change across the
   retained window. Intermediate oscillation is discarded, so a near-zero delta
   does not show that the metric stayed constant.

   Worked example: for values 2 at 0 seconds and 8 at 10 seconds, first = 2,
   last = 8, and delta = :math:`8-2=6`.

   For a memory gauge, delta can describe net accumulation during a fixed
   workload. Its unit is the original metric unit, such as bytes, not bytes per
   second: a 6-byte increase over 10 seconds and over 100 seconds has the same
   delta. Both endpoints are influential, and different window durations can
   make comparisons answer different questions.

``slope``
   Ordinary least-squares slope of value on elapsed seconds. With
   :math:`u_i = (t_i-t_1)` in seconds, it is

   .. math::

      \hat{\beta}_1 =
      \frac{\operatorname{fsum}((u_i-\bar{u})(x_i-\bar{x}))}
      {\operatorname{fsum}((u_i-\bar{u})^2)}.

   Its unit is metric units per second. It is the best linear least-squares
   description of this window, not proof of a causal trend or a valid
   extrapolation. At least two retained points are required; duplicate
   timestamps are rejected before calculation, avoiding a zero time-variation
   denominator for a two-point series.

   Worked example: for :math:`(u, x)=((0, 2), (10, 7))`, the centered-product
   sum is :math:`25` and the centered-time-square sum is :math:`50`; therefore
   slope = :math:`25/50=0.5` metric units per second.

   Use slope to describe sustained memory growth in bytes/second or queue-depth
   drift in items/second. Here :math:`u_i` is elapsed time, :math:`x_i` is the
   corresponding value, and the bars are their arithmetic means. Each centered
   time-value product contributes to the numerator; the denominator measures
   the spread of observation times. Unlike delta, slope uses every retained
   point and accounts for elapsed seconds, though points still receive equal
   weight rather than time-duration weights.

   Curvature, bursts, recovery, or a sawtooth pattern can make a single straight
   line misleading. Outliers, including endpoints far from the mean time, can
   strongly influence the fit. Inspect the series before calling growth
   sustained, and don't extrapolate a short-window slope into a leak forecast.

Choose these summaries and window boundaries before examining which comparison
looks favorable. Selecting a rising segment after seeing the data changes the
question. Neither an endpoint change nor a fitted slope proves that a deployment
caused it; workload changes and shared infrastructure can produce either.

Calculation boundary and failures
---------------------------------

All statistics require a nonempty retained series of finite scalar values.
``std`` and ``slope`` additionally require two points. If calculation
overflows or produces a non-finite result, the metric is marked
``nonfinite_value``. Eligibility failure similarly produces no
substitute scalar. The result records its selected statistic and the exact
eligibility evidence, so downstream comparison can distinguish a valid value
from missing evidence.

From one summary to a cohort
---------------------------------

Suppose two runs have retained values ``(1, 1, 1, 9)`` and ``(5, 5, 5, 5)``.
Their linear P95 values are 7.8 and 5, so the mean of the per-run P95 values
is 6.4. Pooling all eight observations instead gives P95 = 7.6. These answer
different questions even with equal run sizes; unequal sizes also change
the weighting. Perfcheck compares the run-level scalars and doesn't pool
the raw points to make a cohort quantile.

Work through the arithmetic and gate evidence in
`lesson 07 <https://github.com/geoder101/perfcheck/blob/main/examples/07-summary-and-eligibility.py>`_, then follow
:doc:`eligibility-and-comparability` into :doc:`inference-and-power`.
The descriptive formulas explain what a value means. Whether a difference
is precise or practically meaningful is a further question.
