Experimental design for performance evidence
============================================

A statistical method can describe uncertainty in a well-designed experiment;
it can't repair an experiment that compares two different workloads. Before
collecting runs, state the question: for example, "How does the mean per-run
p95 latency change between these builds under this workload on this class of
host?" That names an estimand, the quantity the experiment aims to learn.
It isn't a claim about every request or production environment.

Read :doc:`statistical-foundations` for the vocabulary and
:doc:`probability-and-distributions` for the probability model. This chapter
asks whether that model is plausible for the way the evidence was produced.

Choose the experimental unit before counting samples
----------------------------------------------------

The experimental unit is the entity that receives a condition independently.
For a benchmark that deploys one build and then scrapes a running service,
the unit is often the run, not each scrape. Measurements inside a run share
cache state, host load, configuration, and recent history.

Suppose each of four baseline runs and four current runs supplies 100 latency
scrapes. The comparison has four per-run values on each side, not 400
independent repetitions on each side. Treating all scrapes as independent
replicates is *pseudoreplication*. More scrapes may improve a run's summary,
but don't supply new independent realizations of host and deployment state.

Within-run variation describes the changing values during one run. Between-run
variation describes changes in the selected summary across runs. Consider
two runs with values ``(9, 10, 11)`` and ``(19, 20, 21)`` ms. Both have
within-run sample SD 1 ms, but their means differ by 10 ms. A small within-run
SD doesn't show reproducibility across runs. Conversely, repeated runs might
have similar p95 values even while each run has substantial request-level
spread.

Perfcheck explicitly reduces each eligible metric run to one scalar before
forming a cohort. If the selected statistic is ``p95``, the cohort comparison
uses the mean of *per-run p95 values*. It isn't a pooled request p95 and isn't
automatically a request-weighted population quantity. The method respects the
run-level boundary, but no file format can make runs independent. Reusing a
host's persistent state across every run can still produce dependence.

Separate build effects from environmental effects
-------------------------------------------------

A confounder changes with the build and also affects the outcome. Running all
baseline jobs on an idle morning and all current jobs on a busy afternoon
confounds build and time. If latency rises, either explanation fits.

Where operationally possible, randomize build order and spread repetitions
over the conditions to which the conclusion should apply. Blocking groups
similar conditions, such as host class or time period, so both builds are
represented within each group. Randomization reduces systematic assignment
bias; it doesn't guarantee a balanced result in a small experiment. Blocking
doesn't automatically make measurements paired in the analysis.

For example, a schedule ``baseline, current, current, baseline`` can reduce
alignment with a simple time trend compared with running all baseline jobs
first. It still needs repeated blocks, adequate resets, and a plan for host
load. Avoid overlapping comparison runs to create this schedule: perfcheck
rejects overlapping source intervals. Randomize *sequential* runs instead.

Shared CPU, memory bandwidth, network capacity, or a load generator can create
contention even when benchmark processes are separate. Record relevant
conditions and keep the load generator from becoming the bottleneck. A
randomized schedule can't make an uncontrolled workload represent the
intended one. Perfcheck's policy and provenance checks help identify consistent
inputs; the experimenter remains responsible for environmental comparability.

Paired and unpaired questions
-----------------------------

In a paired design, each current observation has a meaningful baseline partner
defined by the design, such as two conditions measured on the same matched
unit. Analyze the differences :math:`D_i=C_i-B_i`, preserving the matches.
In an unpaired design, the two cohorts have no such one-to-one correspondence;
analysis compares their group summaries without inventing matches.

For an educational paired example, baseline values ``(100, 200, 300)`` and
their matched current values ``(105, 205, 305)`` ms all have differences of
5 ms. The mean difference is 5 ms, and observed spread in those differences
is zero. Each group separately has sample SD 100 ms. Pairing removes the
shared unit-level offsets *in this example*, not in every experiment. Three
perfectly equal observed differences don't establish zero future uncertainty.

The distinction is mathematical as well as procedural:

.. math::

   \operatorname{Var}(C-B)=\operatorname{Var}(C)+\operatorname{Var}(B)
   -2\operatorname{Cov}(C,B).

Positive within-pair covariance can make paired differences more precise.
Incorrectly pairing unrelated observations, or breaking real pairs while
claiming paired precision, changes the uncertainty calculation. Pairing must
be justified before looking at which ordering gives a favorable result.

**Product boundary:** perfcheck's cohort bootstrap is unpaired. It resamples
current and baseline run values separately; positional order and similar file
names don't establish pairs. The CLI doesn't offer a paired-bootstrap mode.
If dependence induced by a matched or blocked design matters, the product's
unpaired evidence isn't a substitute for a design-aware analysis. See
:doc:`comparative-methods` for educational comparisons and
:doc:`uncertainty-and-comparison` for the implemented method.

Warmup, drift, outliers, and missingness
--------------------------------------------

Warmup is an initial transient, such as cache filling or compilation. Decide
whether cold-start or warmed behavior is the target before choosing a trim.
For a steady-state question, a predeclared warmup trim can omit a known
transient. For a cold-start question, the same trim removes the behavior of
interest. Passing the warmup policy doesn't prove steady state.

Drift is change over time, perhaps from thermal throttling, load growth, or a
leak. Inspect the time order as well as the scalar summary. A run moving from
80 to 120 ms can have mean 100 ms, just like a stable run near 100 ms.
The ``slope`` statistic describes a linear trend, but can't identify its cause.
Use consistent durations and a schedule that doesn't align build with drift.

An outlier is an unusually distant observation relative to the chosen model
or other data. It may be a recording error, a genuine rare event, or evidence
that the model misses a regime. Investigate provenance instead of removing
values merely because they change the conclusion. Predeclare exclusions,
apply them symmetrically, and distinguish the primary analysis from any
sensitivity analysis. Perfcheck doesn't provide an automatic statistical
outlier-removal policy; trimming is based on time, not on a value's size.

Missingness is also part of the measurement process. If two of ten current
runs fail only during severe overload, the eight surviving summaries may
look faster than the intended ten-run experiment. Replacing the failures
with zero would make the distortion worse, but excluding them doesn't make
the remaining evidence unbiased. Retain failure counts and reasons, investigate
whether failure depends on performance, and report the scope of the surviving
evidence. Perfcheck records exclusions without imputing substitute values;
its eligibility gates don't diagnose the mechanism of missingness.

A concrete collection plan
--------------------------

For the mean per-run p95 question above, a defensible plan states:

#. The workload, metric unit, build identities, host class, and run duration.
#. The reset procedure, intended warmup state, and fixed time trims.
#. The number of independent runs per condition, allocation schedule, and
   stopping rule, chosen without inspecting whether results favor a build.
#. The per-run statistic and practical effect threshold, chosen for the
   operational question rather than for the most favorable result.
#. Missing-run and invalid-measurement rules, plus what evidence will trigger
   investigation instead of a performance conclusion.
#. Provenance sufficient to reconstruct which builds and conditions produced
   each artifact, without placing secrets in labels, queries, or metadata.

For instance, collect a planned set of runs for each build in a randomly
shuffled, sequential order, applying the same reset and warmup procedure
before each run under one recorded policy. Keep source run identities and
failures. Compare only after the planned collection finishes.
The run count should be motivated by variability and the meaningful effect,
not by a universal rule that a particular small count is enough. Continue to
:doc:`inference-and-power` for that reasoning and :doc:`multiple-testing` for
the consequences of inspecting many metrics or repeatedly checking results.

Reproducibility isn't representativeness
--------------------------------------------

Artifact hashes and seeds help another reader reproduce the recorded
calculation. They can't show that an idle-host benchmark represents a loaded
production fleet. A convenience sample of available CI machines may be useful
for that CI environment while supporting only a narrow deployment claim.

Likewise, eligibility checks establish that a configured measurement window
has enough usable evidence. They aren't tests of IID sampling, absence of
confounding, or causality. Use :doc:`eligibility-and-comparability` and
:download:`lesson 07 <../../examples/07-summary-and-eligibility.py>` to inspect what
the gates actually record, then state the assumptions the design still needs.
