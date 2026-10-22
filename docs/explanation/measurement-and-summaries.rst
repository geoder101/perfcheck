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

   A tail quantile describes a position in this run's retained values, not a
   service-level guarantee. Sparse samples, a short window, or a workload that
   misses rare events can make P90, P95, and especially P99 misleading.

   Worked example: for sorted values :math:`(2, 4, 6, 8)`, P50 has
   :math:`h=1.5` and is :math:`5`; P90 has :math:`h=2.7` and is
   :math:`0.3(6)+0.7(8)=7.4`. The same linear rule gives P95 = 7.7 and
   P99 = 7.94.

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

Ordered and trend summaries
---------------------------

``first``
   The value :math:`x_1` at the earliest retained timestamp. It represents the
   beginning of the analyzed window, not necessarily a cold-start value because
   warmup trimming may have removed earlier observations.

``last``
   The value :math:`x_n` at the latest retained timestamp. It represents the
   end of the analyzed window, not a forecast or a guarantee of steady state.

``delta``
   The endpoint difference :math:`x_n - x_1`. It reports net change across the
   retained window. Intermediate oscillation is discarded, so a near-zero delta
   does not show that the metric stayed constant.

   Worked example: for values 2 at 0 seconds and 8 at 10 seconds, first = 2,
   last = 8, and delta = :math:`8-2=6`.

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

Calculation boundary and failures
---------------------------------

All statistics require a nonempty retained series of finite scalar values.
``std`` and ``slope`` additionally require two points. If calculation
overflows or produces a non-finite result, the metric is marked
``nonfinite_value``. Eligibility failure similarly produces no
substitute scalar. The result records its selected statistic and the exact
eligibility evidence, so downstream comparison can distinguish a valid value
from missing evidence.
