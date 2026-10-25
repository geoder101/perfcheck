Statistical foundations
=======================

This chapter supplies vocabulary for interpreting evidence. It does not turn
performance measurements into proof about every future deployment.

The guiding question is simple: what would change if we repeated the same
measurement procedure? A reported number describes what happened once.
Statistical reasoning asks how that number might vary, which wider quantity
it informs, and which assumptions make that connection reasonable.

Use this reading path as a small book, not a list of formulas to memorize:

#. This chapter identifies populations, samples, and levels of evidence.
#. :doc:`probability-and-distributions` builds models for uncertain outcomes.
#. :doc:`experimental-design` explains how to collect evidence those models
   can reasonably describe.
#. :doc:`measurement-and-summaries` and :doc:`eligibility-and-comparability`
   connect observations to the actual per-run inputs.
#. :doc:`inference-and-power` and :doc:`multiple-testing` develop inference
   and its limits, before :doc:`uncertainty-and-comparison` explains the
   product's fixed comparison procedure.

The mathematical sections are optional on a first reading. Keep the worked
examples and assumptions even if you skip a derivation. The existing
`lesson 06 <../../examples/06-statistical-foundations.py>`_ is a runnable
companion; :doc:`../reference/glossary` is the shared terminology reference.

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

For example, suppose the target is the mean of per-run p95 latencies under a
specified benchmark procedure. Three run summaries, 98, 100, and 108 ms, have
sample mean 102 ms. That is a statistic. The unknown mean across hypothetical
repetitions of that same procedure is a parameter, often called :math:`\mu`.
The population isn't automatically all production requests, and the three
values aren't three individual requests. Naming the target prevents an
accidental change of question halfway through the analysis.

Across repeated samples drawn by the same procedure, a statistic has a
*sampling distribution*. That distribution is background for reasoning about
uncertainty; it is not a product promise that any particular workload produces
independent, identically distributed (IID), or normally distributed values.

An estimator is the rule used before observing the data, such as "take the
mean of the run summaries." The estimate is its realized result, here 102 ms.
If a second experiment produces 99 ms, that difference need not indicate a
mistake. It is the variation the sampling distribution describes. One cohort's
histogram shows its observed run values, not the full sampling distribution
of the mean across repeated experiments.

Description, inference, and causation
------------------------------------

Descriptive statistics summarize the observations at hand. Inference connects
them to unknown quantities under a sampling model. A causal claim goes
further: it attributes a difference to an intervention rather than to other
differences in conditions.

For example, "the current cohort mean is 5 ms higher" is descriptive.
"The procedure tends to produce higher values for this build" requires
uncertainty reasoning and a defensible population. "The build caused the
increase" also requires a design that separates the build from host load,
time, and workload. See :doc:`experimental-design`. Perfcheck records a
policy-based decision from supplied evidence; it doesn't certify the causal
claim or select the population for you.

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

Independence concerns relationships among observations. Identical distribution
concerns the process generating each observation. Four independent runs can
still come from different distributions if two use a different workload.
Four identically configured runs can still be dependent if they share a
persistent overloaded host. "Same policy" and "different run IDs" don't
resolve either issue.

Precision and bias are separate, too. Averaging more runs on an unusually
fast host may make the estimated mean precise for that host without bringing
it closer to the mean across the intended fleet. Larger samples don't cure
an unrepresentative selection mechanism. A useful report states its scope
as carefully as it states its numerical uncertainty.

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

For an intuitive contrast, values 90, 100, and 110 ms have mean 100 ms, as do
99, 100, and 101 ms. Their centers match but their spreads differ. A quantile
answers a different question again: where does a specified fraction of the
distribution lie? Neither spread nor p95 is the standard error of the mean.
The distinction is worked through in :doc:`measurement-and-summaries`;
:doc:`probability-and-distributions` explains CDFs, tails, and p-values.

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

Check your interpretation
-------------------------

Before reading a comparison, complete these sentences:

* "One observed scalar represents ..." Name its run and selected statistic.
* "The wider population I care about is ..." Include workload and environment.
* "Repeating the experiment would mean ..." Specify new runs, not just new
  bootstrap draws from the same data.
* "The connection needs these assumptions ..." Consider independence,
  sampling scope, and whether missing runs change the evidence.

For a cohort of per-run p95 values, a good answer to the first sentence is
"the p95 of retained observations in one eligible run," not "the probability
that this build is slow." That small language check prevents several larger
statistical mistakes.
