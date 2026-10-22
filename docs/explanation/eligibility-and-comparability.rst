Eligibility and comparability
=============================

Eligibility determines whether one raw metric run supplies a scalar summary.
It is a data-quality and scope check, not a hypothesis test. A failed gate
records an explicit reason and produces no replacement value. The later
comparison stage can therefore preserve exclusions and their source run IDs.

Analysis window
---------------

For source interval :math:`[S, E]`, ``warmup_seconds`` removes the inclusive
prefix before :math:`A = S + w`, and ``cooldown_seconds`` removes the inclusive
suffix after :math:`B = E - c`. The analyzed interval is
:math:`[A, \max(A, B)]`; observations at either boundary are retained. Samples
are sorted by timestamp before this filter, so ordered summaries in
:doc:`measurement-and-summaries` use time order rather than arrival order.

``warmup_seconds``
   A nonnegative number of seconds discarded after collection starts. Use it
   when early values are known not to represent the intended measurement state.
   It cannot establish that warmup has completed. An excessive trim can leave a
   window too short or too few points.

   Worked example: if a run begins at 0 seconds and ``warmup_seconds`` is 30,
   the analyzed interval begins at 30 seconds.

``cooldown_seconds``
   A nonnegative number of seconds discarded before collection ends. Use it to
   omit a known shutdown or drain period. It cannot show that the remaining
   interval is stationary. An excessive trim has the same possible failures as
   warmup.

   Worked example: if that run ends at 360 seconds and ``cooldown_seconds`` is
   30, the analyzed interval ends at 330 seconds.

``min_analysis_window_seconds``
   The minimum analyzed duration :math:`B-A` after trimming. Its configured
   minimum is 300 seconds, with a default of 300. If the duration is shorter,
   the reason is ``analysis_window_too_short``. The gate limits very short
   windows, but does not make a longer window representative.

   Worked example: the 30--330 second interval above lasts 300 seconds and
   meets the default; trimming it to 299 seconds yields
   ``analysis_window_too_short``.

Point count and coverage
------------------------

With policy step :math:`d` seconds and analyzed duration :math:`D`, the
expected count is

.. math::

   N_{\mathrm{expected}} = \left\lfloor\frac{D}{d}\right\rfloor + 1.

The observed count is the number of retained samples, and coverage is

.. math::

   \mathrm{coverage} = \frac{N_{\mathrm{retained}}}{N_{\mathrm{expected}}}.

``min_points``
   The minimum retained count, configured no lower than 20 and defaulting to
   20. Fewer points yield ``insufficient_points``. This is separate from the
   two-point requirement for ``std`` and ``slope``, which yields
   ``statistic_requires_more_points`` first. Count alone says nothing about
   temporal spacing.

   Worked example: at a 15-second step, a 300-second window expects 21 points.
   Retaining 20 points meets the default ``min_points`` of 20.

``min_coverage``
   The minimum retained-to-expected ratio, configured no lower than 0.8 and
   defaulting to 0.8. A smaller ratio yields ``coverage_too_low``. Coverage can
   still pass when missing observations are clustered, so it is paired with the
   gap gate below.

   Worked example: 20 retained points out of 21 expected have coverage
   :math:`20/21 \approx 0.952`, which meets 0.8; 16 out of 21 have coverage
   :math:`16/21 \approx 0.762`, which yields ``coverage_too_low``.

Gaps
----

``max_gap_steps``
   A nonnegative allowance for missing step intervals, defaulting to 3. The
   maximum permitted duration is

   .. math::

      G_{\max} = (\mathit{max\_gap\_steps}+1)d.

   The check takes the largest of the leading gap from :math:`A` to the first
   sample, every adjacent timestamp gap, and the trailing gap from the last
   sample to :math:`B`. A larger gap yields ``gap_too_large``. The gate detects
   a large absence but cannot diagnose why observations are absent.

   Worked example: with a 15-second step and ``max_gap_steps`` of 3,
   :math:`G_{\max}=(3+1)15=60` seconds. A 75-second adjacent gap yields
   ``gap_too_large``.

Input integrity and no imputation
---------------------------------

Before policy gates, an empty raw series yields ``empty_series``; any NaN or
infinite raw value yields ``nonfinite_value``; and repeated timestamps yield
``duplicate_timestamp``. If a selected statistic overflows or is non-finite,
it also yields ``nonfinite_value``. These checks require eligible scalar
evidence, rather than silently accepting a problematic value.

The system does not impute, interpolate, carry forward, or synthesize missing
points. Missing points reduce coverage and may create a gap. When any
eligibility gate fails, no summary value is written for that metric. When
cohorts are assembled, a missing metric, an unavailable metric, or an
ineligible summary is excluded with its exact reason instead of being replaced
by zero, a mean, or another estimate.

Comparability of usable runs
----------------------------

A usable per-run scalar carries its source run ID, source artifact hash,
source interval, policy hash, and compatibility fingerprints for the policy's
metrics. Comparison retains those inputs and the exclusions, allowing the
decision record to identify which runs supplied evidence. The summary artifact
also requires the selected statistic to match the metric policy.

These checks establish consistent, traceable inputs for a configured policy.
They do not prove independence, equal distributions, causal comparability, or
representativeness. Interpret those assumptions using the cautions in
:doc:`statistical-foundations`, not as consequences of an eligibility pass.
