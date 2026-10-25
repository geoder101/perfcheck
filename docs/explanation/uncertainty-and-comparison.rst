Uncertainty and comparison
===========================

``compare`` evaluates eligible scalar summaries from a current cohort against a
baseline cohort under one policy. It produces reproducible evidence for that
configured comparison. It does not establish that either cohort represents all
future deployments.

Prerequisites are :doc:`probability-and-distributions` for sampling distributions
and :doc:`experimental-design` for choosing independent runs. For classical
p-values, coverage and power, read :doc:`inference-and-power`. This chapter
describes the implemented numerical contract, not an exact inference theorem.

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
policy's direction. Ordinary latency is **higher-is-worse**: baseline 80 ms and
current 90 ms give :math:`90-80=+10` ms without changing signs. Throughput is
ordinarily **lower-is-worse**: baseline 1000 requests/s and current 900 requests/s
become -1000 and -900, giving :math:`-900-(-1000)=+100` requests/s of worsening.
A throughput increase to 1100 instead gives :math:`-1100-(-1000)=-100`, an
improvement. These are differences in original units, not percentages or ratios.
The configured direction controls the calculation; a mislabeled policy cannot
be repaired by statistical resampling.

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
Enabled metrics that later become inconclusive still count in the denominator.
The union-bound argument and its calibration premise are derived in
:doc:`multiple-testing`. A nominal allocation is not proof that an approximate
bootstrap decision achieves a 5% family-wise false-failure rate.

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

Each metric starts a fresh generator with the selected seed. Within each
replicate, production draws the current cohort first and the baseline second.
Changing input order, generator, draw order, arithmetic or quantile convention
can change the result even if the headline seed is unchanged. Reproducibility
requires the recorded numerical contract, not merely the word "bootstrap".

Why resampling might approximate uncertainty
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The empirical distribution assigns probability :math:`1/n` to each of a
cohort's :math:`n` observed run values. Sampling from it replaces an unknown
population by the observed distribution. Repeating a statistic on these samples
approximates how that statistic might vary if the empirical distribution were
the population. It doesn't simulate new deployments from a validated workload
model and doesn't make the original cohort larger.

For an independent sample and a sufficiently regular statistic, the empirical
distribution can approximate features of the population well enough to make
bootstrap inference useful. A difference of means is a natural candidate, but
finite variance, adequate tail information and a suitable sampling design still
matter. Here each input is already one run-level summary; bootstrapping run
means estimates variability across run means, not request-level latency
variability. Bootstrapping run p99 values concerns the mean of those run p99
values, not the p99 of all requests pooled across runs.

The bootstrap distribution is centered near the observed effect. It isn't a
null distribution constructed under "no regression". Counting its negative
replicates and labeling the fraction a p-value would require a separate
justification. The production method doesn't do that.

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

Where the approximation can fail
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ordinary within-cohort resampling treats run values as exchangeable independent
draws from stable cohort populations. Adjacent runs can instead share cache
state, hardware contention or traffic conditions. Then an IID bootstrap may
understate uncertainty by treating correlated information as fresh information.
Paired baseline/current measurements also require preserving the pairs to
estimate their dependence; independent cohort resampling doesn't do so.
Block, paired or hierarchical resampling are possible statistical alternatives,
but aren't implemented modes and need a design-specific justification.

A small cohort can't reveal rare slow runs that never occurred in it. Heavy
tails can make means and tail quantiles unstable; infinite-variance settings
can invalidate familiar mean-bootstrap asymptotics. Skewness, estimator bias,
unequal cohort sizes and finite samples can impair percentile coverage even
when observations are independent. Constant observed values produce a
degenerate bootstrap distribution, not proof that the real workload has zero
variance. Neither minimum run counts nor a small-sample warning validate a
coverage claim.

There are two separate sources of uncertainty:

* **Sampling uncertainty:** which original runs were collected. More independent,
  representative runs can improve this information; resampling can't invent it.
* **Monte Carlo error:** approximating a bootstrap distribution with finitely
  many replicates. More resamples can reduce this numerical error but cannot
  repair bias, dependence or an unrepresentative cohort.

For intuition, at the floor :math:`B=2000m` the expected number of draws below
a continuous bootstrap population's :math:`0.05/m` quantile is only
:math:`B(0.05/m)=100`. The probability-scale SD of an empirical tail fraction
is roughly :math:`\sqrt{a(1-a)/B}` for :math:`a=0.05/m`, conditional on the
original data and independent draws. Quantile error in measurement units also
depends on the distribution's local density; 100 tail draws don't guarantee a
particular bound accuracy. Ties and interpolation complicate that intuition.
Trying seeds until a desired verdict appears is selection, not validation.

Demonstrated calibration would require studying repeated datasets under
specified workload-generating processes, measuring coverage or false-failure
rates with uncertainty, and checking whether those processes represent the
intended use. Fixed-seed fixtures check arithmetic and reproducibility. They
don't supply that calibration evidence or a universal coverage guarantee.

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

An empirical upper baseline quantile isn't automatically a prediction bound
for a future run. Its tail uncertainty, baseline size and possible drift still
matter. The advisory status prevents treating this single-current contrast as
the multi-run bootstrap decision.

Continue with :doc:`decisions-and-limitations` for strict threshold boundaries,
then :doc:`plain-python-mechanics` for transparent arithmetic.
:download:`Lab 08 <../../examples/08-bootstrap-and-decisions.py>` demonstrates
the product rule; :download:`Lab 10 <../../examples/10-comparative-methods.py>`
contrasts methods that don't determine its verdicts.
