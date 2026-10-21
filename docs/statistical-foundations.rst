Statistical foundations
=======================

This chapter supplies vocabulary for interpreting evidence. It does not turn
performance measurements into proof about every future deployment.

From observations to evidence
-----------------------------

A *population* is the wider collection about which someone might want to make
a claim: for example, all requests a service could receive under a stated
workload and environment. A *sample* is the finite set of observed values used
to learn about that population. One observed sample is a *realization* of a
random process or measurement procedure.

A statistical *model* describes how observations could arise. Its *parameters*
are unknown population-level quantities, while a *statistic* is a number
calculated from observed data. For values ``x_1, ..., x_n``, the sample mean is
the statistic

.. math::

   \bar{x} = \frac{1}{n}\sum_{i=1}^{n}x_i.

Across repeated samples drawn by the same procedure, a statistic has a
*sampling distribution*. That distribution is background for reasoning about
uncertainty; it is not a product promise that any particular workload produces
independent, identically distributed (IID), or normally distributed values.

IID, convenience samples, and convergence
------------------------------------------

IID is a useful idealization: observations are independent and share a common
distribution. Time-series performance data can violate either part through
cache state, traffic bursts, deploys, retries, or shared infrastructure. A
convenience sample is simply the data that was easy to collect; it may not
represent the population of interest. These limitations must be considered
before interpreting a stable-looking scalar as a general claim.

The law of large numbers and central limit theorem (CLT) motivate familiar
large-sample intuition under their assumptions. In particular, suitably
standardized sample means often approach a normal distribution as the sample
size grows. Neither convergence result establishes that the inputs to a
specific perfcheck run are IID, representative, or sufficiently numerous.

Location, spread, and distribution functions
---------------------------------------------

Expectation is a population-level long-run average, commonly written
:math:`\operatorname{E}[X]`. Variance and standard deviation quantify spread
around that expectation:

.. math::

   \operatorname{Var}(X) = \operatorname{E}[(X - \operatorname{E}[X])^2],
   \qquad \operatorname{SD}(X) = \sqrt{\operatorname{Var}(X)}.

For a random variable :math:`X`, its cumulative distribution function (CDF) is

.. math::

   F_X(x) = \Pr(X \leq x).

A quantile at probability :math:`p` is a value at which the CDF reaches or
exceeds :math:`p`; a percentile is the same idea expressed on a 0--100 scale.
Quantiles summarize position in a distribution, but their estimate depends on
the finite sample and the selected numerical convention.

Artifact bridge: raw run to cohort
----------------------------------

The CLI evidence flow keeps these levels distinct:

#. ``collect`` writes a *raw run*: timestamped metric observations over a
   source interval. These are observed values, not a population.
#. ``summarize`` writes one source-hashed *summary artifact* per raw run. For
   each available metric, eligibility evidence determines whether a selected
   summary statistic has a finite scalar value. An ineligible metric has an
   explicit reason rather than an imputed value.
#. ``compare`` forms baseline and current *cohorts* from usable per-run scalar
   inputs, retaining run provenance and exclusions. A cohort is an evidence
   set for a metric, not a claim that its members are an IID sample.

The later comparison policy evaluates these validated inputs. This foundational
mapping explains what each object represents; it does not specify an
alternative inference method or guarantee product validity.
