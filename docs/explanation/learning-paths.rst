Learning paths
==============

Choose a route, not a second set of chapters. Each route reuses the same
explanations and ten numbered Marimo lessons. The CLI is the only supported
public interface; educational helpers and alternative methods aren't product
features. See "Running the labs" below for local setup and per-lesson commands.

Beginner: build the vocabulary
-----------------------------------

#. Start with :doc:`../tutorials/first-comparison` and lessons 01-04 to see
   ``collect`` -> ``summarize`` -> ``compare`` produce real evidence.
#. Read :doc:`statistical-foundations`, then
   :doc:`probability-and-distributions`; use lab 06 to distinguish point mass,
   tail probability, density, and the sampling distribution of a mean.
#. Read :doc:`measurement-and-summaries` and
   :doc:`eligibility-and-comparability`, then lab 07 to connect observations
   to one eligible value per run.
#. Finish with :doc:`decisions-and-limitations` and lesson 05's selected CLI
   scenario. Explain why PASS isn't proof of equivalence.

Practitioner: plan and audit a performance check
----------------------------------------------------

#. Read :doc:`experimental-design` before choosing workloads, independent runs,
   exclusions, and a stopping rule; lab 07 exposes pseudoreplication and drift.
#. Follow :doc:`../tutorials/performance-verification-case-study` with lesson
   05's pass, regression, and advisory-reference selector. Inspect artifacts
   and distinguish statistical verdicts from input-error exit status 3.
#. Read :doc:`uncertainty-and-comparison`, :doc:`inference-and-power`, and
   :doc:`multiple-testing`; use lab 08 to vary orientation, practical threshold,
   and enabled-metric count without confusing a decision bound with a p-value.
#. Revisit :doc:`decisions-and-limitations` before setting CI behavior for
   FAIL and INCONCLUSIVE. More bootstrap draws aren't more independent runs.

Deep dive: examine models and calculations
----------------------------------------------

#. Work through :doc:`probability-and-distributions` and
   :doc:`experimental-design` with labs 06-07, checking their assumptions.
#. Derive the tests, confidence intervals, and planning formulas in
   :doc:`inference-and-power`; compare lab 08's repeated known-sigma intervals
   with its separate bootstrap experiment.
#. Read :doc:`plain-python-mechanics` with lab 09 to inspect quantile
   interpolation and why orientation happens before sorting.
#. Read :doc:`multiple-testing` and :doc:`comparative-methods` with lab 10.
   Explore null calibration, power, and none/Bonferroni/Holm/BH families while
   keeping those teaching procedures separate from perfcheck verdicts.

Running the labs
----------------

Native setup requires Just, uv, and Python 3.14; the
project's root ``README.md`` owns the full prerequisites.
Run ``just sync`` from the repository root to install the locked
dev/docs/examples groups, a broader environment than examples-only setup.
Run lesson commands from that same root. Open the
selected lesson with ``just notebook-run examples/`` followed by its filename
as the single required path argument. Use ``just notebook-edit`` with that path
to author it, or ``just notebook-script`` with that path to run the same default
controls without a browser. Download the `curriculum index <https://github.com/geoder101/perfcheck/blob/main/examples/README.md>`_
for all ten filenames and explicit author, consumer, and script commands.
Start there for control descriptions; the routes above don't add lessons.
