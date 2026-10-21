Uncertainty and comparison
===========================

``compare`` evaluates eligible scalar summaries from a current cohort against a
baseline cohort under one policy. It produces reproducible evidence for that
configured comparison. It does not establish that either cohort represents all
future deployments.

Orientation and comparable cohorts
----------------------------------

Each metric policy declares whether larger values are worse or smaller values
are worse. Before comparison, a value :math:`x` is transformed to an oriented
value :math:`z`:

.. math::

   z =
   \begin{cases}
   x, & \text{higher is worse};\\
   -x, & \text{lower is worse}.
   \end{cases}

For either direction, the observed effect is then

.. math::

   \widehat{\Delta} = \overline{z}_{\mathrm{current}}
   - \overline{z}_{\mathrm{baseline}}.

A positive effect therefore always means the current cohort is worse in the
policy's direction. For example, if latency is lower-is-worse, a current mean
of 90 ms and baseline mean of 80 ms become -90 and -80, so the oriented effect
is :math:`-90 - (-80) = 10`. A throughput metric configured as
higher-is-worse needs no sign change.

Before selecting a method, perfcheck requires all supplied runs to carry the
selected policy hash and the expected metric fingerprints. A fingerprint covers
the suite identifier, metric identifier, query, expected labels, unit,
direction, statistic, step, rate window, eligibility policy, and policy schema
version. Source run IDs and source content hashes must each be globally unique
across both cohorts, and source time intervals may not overlap. These checks
make the recorded inputs traceable and consistently configured. They do not
prove independence, exchangeability, representativeness, or causal similarity.

Alpha across enabled gates
--------------------------

The policy fixes ``nominal_alpha`` at 0.05. If :math:`m` metrics are enabled as
gates, perfcheck uses the Bonferroni effective alpha

.. math::

   \alpha_{\mathrm{effective}} =
   \frac{\alpha_{\mathrm{nominal}}}{m}.

For example, with three enabled metrics, the effective alpha is
:math:`0.05 / 3`. Disabled metrics do not increase :math:`m`. This is a fixed
family-wise adjustment for the configured gates, not a general multiple-testing
framework or a claim about every possible metric someone could inspect.

Cohort bootstrap evidence
--------------------------

The cohort-bootstrap method requires at least the policy's minimum current and
baseline run counts. In ``auto`` mode it is selected when there is more than
one current run. Each bootstrap replicate samples, with replacement, as many
oriented values as appear in each original cohort. It calculates

.. math::

   \Delta^{*(b)} = \overline{z}^{*(b)}_{\mathrm{current}}
   - \overline{z}^{*(b)}_{\mathrm{baseline}}

for replicate :math:`b`. The resulting finite collection of mean differences
is an empirical bootstrap distribution.

Sampling uses NumPy's ``PCG64`` generator. The default seed is 42 and the
default requested resample count is 10,000, so the same ordered inputs and
options reproduce the same draws. The effective count is

.. math::

   B_{\mathrm{effective}} =
   \max(B_{\mathrm{requested}}, 2000m),

where :math:`m` is the enabled metric count. The report retains the seed,
requested count, and effective count because they are part of the numerical
provenance. It uses float64 arithmetic for these calculations.

Bounds and their meanings
-------------------------

Perfcheck takes quantiles with NumPy's ``method="linear"`` convention. The
decision bound is the empirical quantile at
:math:`\alpha_{\mathrm{effective}}`:

.. math::

   L_{\mathrm{decision}} = Q_{\alpha_{\mathrm{effective}}}
   (\Delta^{*(1)}, \ldots, \Delta^{*(B_{\mathrm{effective}})}).

It also records diagnostic lower and upper bounds at 0.025 and 0.975. Those
diagnostics help readers see the spread of the sampled effects, while the
decision uses only :math:`L_{\mathrm{decision}}`. A quantile's value depends on
the finite draws and the chosen interpolation convention.

These percentile-bootstrap bounds are not p-values. They are also not a claim
that normality, IID sampling, or a particular confidence-interval coverage
guarantee holds for a performance workload. A classical confidence interval is
an interval-producing procedure with an interpretation tied to its sampling
assumptions and repeated use. perfcheck records deterministic percentile
bootstrap evidence and a policy rule instead of exposing a general confidence
interval procedure.

Baseline reference evidence
---------------------------

Baseline-reference mode requires exactly one current run and at least the
policy's minimum reference-baseline count. In ``auto`` mode, one current run
selects this method when the baseline count is sufficient. It has no seed,
resamples, or bootstrap interval.

The method takes the upper baseline-tail quantile of the oriented values:

.. math::

   q_{\mathrm{reference}} = Q_{1-\alpha_{\mathrm{effective}}}
   (z_{\mathrm{baseline}}),
   \qquad
   \Delta_{\mathrm{reference}} = \overline{z}_{\mathrm{current}}
   - q_{\mathrm{reference}}.

It marks ``reference_anomaly`` when
:math:`\Delta_{\mathrm{reference}}` is strictly greater than the practical
threshold. That flag is advisory evidence only. A baseline-reference metric
remains ``INCONCLUSIVE`` even when it records an anomaly, and it does not make
the suite fail.
