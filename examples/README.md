# perfcheck Marimo curriculum

These developer learning materials teach the supported `perfcheck` CLI workflow.
The CLI remains the only supported public surface. Lessons are self-contained and
write any artifacts only to temporary workspaces.

## Choose a learning route

The [learning paths](https://geoder101.github.io/perfcheck/explanation/learning-paths.html) reuse these eleven
lessons and the existing chapters rather than introducing another course:

- **Beginner:** CLI lessons 01–04, probability lab 06, summaries lab 07, then
  lesson 05 to interpret verdicts and input errors.
- **Practitioner:** experimental design and lab 07, the
  [performance verification case study](https://geoder101.github.io/perfcheck/tutorials/performance-verification-case-study.html)
  with capstone 05, then lab 08 and the inference and multiple-testing chapters.
- **Deep dive:** probability/design labs 06–07, inference lab 08, mechanics
  lab 09, and power/multiplicity lab 10 with their linked explanations.

Numeric order remains the complete course. The routes select an emphasis;
alternative statistical teaching models do not determine perfcheck PASS/FAIL.

## Setup

Native setup requires Just, uv, and Python 3.14 or later. See the
[root installation guide](../README.md) for full prerequisites.
Run setup and all lesson commands from the repository root:

```bash
just sync
```

`just sync` installs the locked dev/docs/examples groups, a broader environment
than the minimal examples-only dependencies.

Start every lesson with ``just notebook-edit``: this opens the lesson in Marimo's
editor, where you run each cell in turn, editing the code and re-running as you
learn. This is the way to go through a lesson. Once you have read a control-driven
lesson (05 through 10), try ``just notebook-run`` to feel its sliders and selectors
with the code hidden. Reach for ``just notebook-script`` only when you have no
browser -- to verify that a lesson runs clean end to end, or to reproduce it on a
headless machine or CI runner; it executes the whole notebook at once without
interacting. Each Just recipe takes one required notebook path. Authoring uses
`uv run --group examples marimo edit` internally; script execution uses
`uv --directory . run --group examples python` internally.
Direct `uv` commands remain in the tutorials for standalone fixture-server
operations, which have no recipe. Quoted CLI workflows also stay direct to
preserve argument boundaries and the application's exit status.

Once dependencies are installed, lessons use repository content, inline charts,
and local controls without required external HTTP fetches or hosted chart services.
CLI exercises use loopback fixtures; optional external citations are links to
follow, not embedded resources. Dependency installation may require network access.

## Lessons

Start at 01, then continue in numeric
order. Begin each lesson with ``just notebook-edit`` from the repository root;
the ``run`` and ``script`` commands listed under each entry are the app-view and
headless alternatives described above.

### 01. [01-overview.py](01-overview.py), workflow overview

- **Goal:** learn the collect, summarize, and compare evidence flow.
- **Prerequisite:** setup above.
- **CLI commands exercised:** `perfcheck collect`, `perfcheck summarize`, and
  `perfcheck compare`.
- **Author:** `just notebook-edit examples/01-overview.py`
- **Consumer:** `just notebook-run examples/01-overview.py`
- **Script:** `just notebook-script examples/01-overview.py`

### 02. [02-collect.py](02-collect.py), collect a raw run

- **Goal:** collect deterministic raw performance evidence.
- **Prerequisite:** complete 01.
- **CLI commands exercised:** `perfcheck collect`.
- **Author:** `just notebook-edit examples/02-collect.py`
- **Consumer:** `just notebook-run examples/02-collect.py`
- **Script:** `just notebook-script examples/02-collect.py`

### 03. [03-summarize.py](03-summarize.py), verify and summarize evidence

- **Goal:** verify raw evidence and create a canonical summary.
- **Prerequisite:** complete 02.
- **CLI commands exercised:** `perfcheck summarize`.
- **Author:** `just notebook-edit examples/03-summarize.py`
- **Consumer:** `just notebook-run examples/03-summarize.py`
- **Script:** `just notebook-script examples/03-summarize.py`

### 04. [04-compare.py](04-compare.py), compare cohorts

- **Goal:** compare baseline and current evidence under a policy.
- **Prerequisite:** complete 03.
- **CLI commands exercised:** `perfcheck collect`, `perfcheck summarize`, and
  `perfcheck compare`.
- **Author:** `just notebook-edit examples/04-compare.py`
- **Consumer:** `just notebook-run examples/04-compare.py`
- **Script:** `just notebook-script examples/04-compare.py`

### 05. [05-failures-and-ci.py](05-failures-and-ci.py), handle failures in CI

- **Goal:** inspect a safe nonzero CLI result and its CI meaning.
- **Interactive control:** choose `pass`, `regression`, or `advisory-reference`
  in the CLI scenario selector. Only that scenario runs, using fresh temporary
  artifacts and the real collect, summarize, and compare commands; script mode
  uses `pass`. Inspect the report and the separately handled overwrite error.
- **Prerequisite:** complete 04.
- **CLI commands exercised:** `perfcheck compare`.
- **Author:** `just notebook-edit examples/05-failures-and-ci.py`
- **Consumer:** `just notebook-run examples/05-failures-and-ci.py`
- **Script:** `just notebook-script examples/05-failures-and-ci.py`

### 06. [06-statistical-foundations.py](06-statistical-foundations.py), statistical foundations

- **Goal:** distinguish populations, samples, realizations, and sampling distributions.
- **Interactive controls:** vary fair flips, observed heads, repeated experiments,
  IID sample size, and the standard-normal interval. Compare point mass with an
  upper tail, density with area/CDF, and individual spread with mean spread.
- **Explanation:** [Probability and distributions](https://geoder101.github.io/perfcheck/explanation/probability-and-distributions.html).
- **Prerequisite:** complete 05.
- **CLI command explained:** the collect-to-compare evidence flow.
- **Author:** `just notebook-edit examples/06-statistical-foundations.py`
- **Consumer:** `just notebook-run examples/06-statistical-foundations.py`
- **Script:** `just notebook-script examples/06-statistical-foundations.py`

### 07. [07-summary-and-eligibility.py](07-summary-and-eligibility.py), summaries and eligibility

- **Goal:** calculate fixed per-run summaries and inspect eligibility evidence.
- **Interactive controls:** vary readings per run and independent runs, then
  balance treatment/control across time. Contrast naive and run-level uncertainty
  and confounded versus balanced schedules; eligibility alone doesn't establish IID.
- **Explanation:** [Experimental design](https://geoder101.github.io/perfcheck/explanation/experimental-design.html).
- **Prerequisite:** complete 06.
- **CLI command explained:** `perfcheck summarize`.
- **Author:** `just notebook-edit examples/07-summary-and-eligibility.py`
- **Consumer:** `just notebook-run examples/07-summary-and-eligibility.py`
- **Script:** `just notebook-script examples/07-summary-and-eligibility.py`

### 08. [08-bootstrap-and-decisions.py](08-bootstrap-and-decisions.py), bootstrap decisions

- **Goal:** inspect oriented bootstrap evidence, advisory references, and limits.
- **Interactive controls:** change direction, current shift, practical threshold,
  enabled-metric count, and PCG64 seed. Separately vary known-sigma CI sample size,
  sigma, confidence, and repetitions to inspect achieved coverage, not a posterior.
- **Explanation:** [Inference and power](https://geoder101.github.io/perfcheck/explanation/inference-and-power.html).
- **Prerequisite:** complete 07.
- **CLI command explained:** `perfcheck compare`.
- **Author:** `just notebook-edit examples/08-bootstrap-and-decisions.py`
- **Consumer:** `just notebook-run examples/08-bootstrap-and-decisions.py`
- **Script:** `just notebook-script examples/08-bootstrap-and-decisions.py`

### 09. [09-plain-python-mechanics.py](09-plain-python-mechanics.py), plain-Python mechanics

- **Goal:** expose mean, linear quantiles, sample spread, slope, and seeded resampling.
- **Interactive controls:** move the linear-quantile slider and toggle the
  lower-throughput-is-worse checkbox; compare negating before sorting with
  negating a raw quantile afterward. The Python RNG remains teaching-only.
- **Prerequisite:** complete 08.
- **CLI commands explained:** `perfcheck summarize` and `perfcheck compare`; no CLI invocation.
- **Boundary:** educational `random.Random` draws are not production NumPy PCG64 evidence.
- **Explanation:** [Plain-Python mechanics](https://geoder101.github.io/perfcheck/explanation/plain-python-mechanics.html).
- **Author:** `just notebook-edit examples/09-plain-python-mechanics.py`
- **Consumer:** `just notebook-run examples/09-plain-python-mechanics.py`
- **Script:** `just notebook-script examples/09-plain-python-mechanics.py`

### 10. [10-comparative-methods.py](10-comparative-methods.py), comparative methods

- **Goal:** contrast Welch/t, seeded permutation, tied ranks, and a simple posterior.
- **Interactive controls:** change null repetitions/seed; power effect, sample
  size, known sigma, and alpha; then family size, true-null count, alpha,
  repetitions/seed, and none/Bonferroni/Holm/BH adjustment. Inspect FWER and FDP
  separately, with simulation uncertainty rather than a guarantee for one family.
- **Multiplicity explanation:** [Multiple testing](https://geoder101.github.io/perfcheck/explanation/multiple-testing.html).
- **Prerequisite:** complete 09.
- **CLI command explained:** `perfcheck compare`; no CLI invocation or new policy.
- **Boundary:** each method does not determine perfcheck PASS/FAIL.
- **Explanation:** [Comparative methods](https://geoder101.github.io/perfcheck/explanation/comparative-methods.html).
- **Author:** `just notebook-edit examples/10-comparative-methods.py`
- **Consumer:** `just notebook-run examples/10-comparative-methods.py`
- **Script:** `just notebook-script examples/10-comparative-methods.py`

### 11. [11-comparison-internal-trace.py](11-comparison-internal-trace.py), comparison internal trace

- **Goal:** trace the internal comparison flow end to end with a faithful, transparent mirror of the collect → summarize → compare decision core.
- **Interactive controls:** change direction, practical threshold, current value, current and baseline run counts, enabled-metric count, and PCG64 seed; recompute the trace live.
- **Explanation:** [Comparative methods](https://geoder101.github.io/perfcheck/explanation/comparative-methods.html).
- **Prerequisite:** complete 10.
- **CLI commands explained:** none; no CLI invocation — the lesson mirrors the comparison core directly instead of calling `perfcheck`.
- **Author:** `just notebook-edit examples/11-comparison-internal-trace.py`
- **Consumer:** `just notebook-run examples/11-comparison-internal-trace.py`
- **Script:** `just notebook-script examples/11-comparison-internal-trace.py`
