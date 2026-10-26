Performance verification: a CLI case study
===========================================

Goal and question
-----------------

Is current **mean latency in seconds** worse than baseline under a policy chosen
before examining outcomes? This case study follows timestamped observations into
verified per-run summaries and an actual JSON/Markdown decision report. It needs
only this checkout, Python 3.14 and ``uv``; no remote Prometheus or load generator
is required. The supported interface is the public ``perfcheck`` CLI, not the
educational Python helpers or internal artifact schemas.

Inputs and experimental plan
----------------------------

The bundled policy declares ``latency``, statistic ``mean``, unit ``seconds``,
direction ``higher_is_worse`` and practical threshold **0 seconds**. Positive
oriented effects mean worse latency. Zero is a deliberately simple fixture
threshold, not a production recommendation or a calibrated detectable effect.

Plan two baseline runs followed by two current runs, using the ten-minute UTC
intervals on July 11, 12, 13 and 14, 2026. The advisory-reference variant instead
plans two baseline runs and exactly one current run. These are the existing
fixtures' reduced minima, **not a power calculation or statistical calibration**.
Do not change the threshold or add runs only because an observed verdict is
unwelcome. A real study should pre-plan a representative workload, run budget,
environment controls and practically meaningful threshold.

The local fixture supplies 41 timestamped values per run, 15 seconds apart.
It assigns timestamps from each CLI request; the notebook does not wait ten
minutes or benchmark a service. Pass uses constant 10-second values in all runs.
Regression uses baseline 10 and current 20. Reference uses baseline 10 and
current 20 in the capstone's temporary matrix variant. The extreme, noiseless
numbers deliberately make the reporting path easy to audit.

Warmup and cooldown are both **0 seconds** in these policies. Eligibility requires
at least 20 retained points, a 300-second analysis window, coverage at least 0.8,
and at most three missing 15-second steps, permitting leading, adjacent and
trailing gaps up to 60 seconds. Full fixture runs retain 41 points over 600
seconds with coverage 1.0. Those gates establish usable input, not
independence, exchangeability, representativeness or steady state. In particular,
41 observations in one run are not 41 independent runs in a comparison cohort.

Run the complete selected scenario
------------------------------------------------------------

From the repository root:

.. code-block:: console

   $ uv sync --group examples
   $ uv run --group examples marimo run examples/05-failures-and-ci.py

The native Marimo selector offers ``pass`` (default), ``regression`` and
``advisory-reference``. Only the selected scenario executes. Each selection
creates a fresh temporary directory and loopback fixture process, calls the real
``collect``, ``summarize`` and ``compare`` commands, displays actual artifact
excerpts and cleans up. Changing the selection does not reuse prior evidence.
The script form runs the default pass scenario without a browser:

.. code-block:: console

   $ uv run --group examples python examples/05-failures-and-ci.py

Inspect the CLI steps yourself
------------------------------------------------------------

The following POSIX-shell commands reproduce the pass workflow with files you
can inspect. Unlike the notebook, these outputs remain until you remove the
temporary directory. Run from the repository root. First, in terminal A, start
the synthetic service and wait for its printed loopback endpoint:

.. code-block:: console

   $ uv run python examples/fixtures/mock_prometheus.py --port 18090 --fixture examples/fixtures/prometheus-matrix.json

If that local port is occupied, choose a free one and change the explicit
``--prometheus-url`` below. No external service is needed. In terminal B, also
at the repository root:

.. code-block:: sh

   ROOT="$PWD"
   WORK="$(mktemp -d)"
   POLICY="$ROOT/tests/fixtures/policy-pass.json"
   for spec in baseline-1:11 baseline-2:12 current-1:13 current-2:14; do
       name="${spec%:*}"
       day="${spec#*:}"
       uv run perfcheck collect --suite "$POLICY" \
           --prometheus-url http://127.0.0.1:18090 \
           --run-id "failure-$name" \
           --start "2026-07-${day}T10:00:00Z" \
           --end "2026-07-${day}T10:10:00Z" \
           --out "$WORK/$name.json" || break
       uv run perfcheck summarize --policy "$POLICY" \
           --run "$WORK/$name.json" \
           --out "$WORK/$name.summary.json" || break
   done
   uv run perfcheck compare --policy "$POLICY" \
       --baseline "$WORK/baseline-1.summary.json" \
       --baseline "$WORK/baseline-2.summary.json" \
       --current "$WORK/current-1.summary.json" \
       --current "$WORK/current-2.summary.json" \
       --report-json "$WORK/comparison.json" \
       --report-md "$WORK/comparison.md" --seed 20260705 --resamples 1000
   code=$?
   printf 'compare exit status: %s\n' "$code"

Inspect both report files in ``$WORK`` before cleanup. To reproduce regression,
stop terminal A's fixture with Ctrl-C and start it again so query counters reset;
use a fresh ``WORK``, set ``POLICY`` to ``tests/fixtures/policy-fail.json`` under
``$ROOT``, and repeat the same four-run commands. The fixture's ``fail_metric``
query supplies 10, 10, 20, 20 in collection order. Always use the selected policy
for **all three stages**; never mix summaries from pass and regression policies.

For the capstone's elevated reference variant, first stop the fixture. In
terminal B create a fresh ``WORK`` and its local matrix:

.. code-block:: sh

   WORK="$(mktemp -d)"
   POLICY="$ROOT/tests/fixtures/policy-inconclusive.json"
   printf '%s\n' '{"sample_count":41,"queries":{"inconclusive_metric":[10.0,10.0,20.0]}}' > "$WORK/reference-matrix.json"
   printf 'fixture path: %s\n' "$WORK/reference-matrix.json"

In terminal A run the same fixture command with ``--fixture`` pointing to that
printed absolute path. Repeat the collect/summarize loop with only
``baseline-1:11 baseline-2:12 current-1:13``. Then compare:

.. code-block:: sh

   uv run perfcheck compare --policy "$POLICY" \
       --baseline "$WORK/baseline-1.summary.json" \
       --baseline "$WORK/baseline-2.summary.json" \
       --current "$WORK/current-1.summary.json" \
       --report-json "$WORK/comparison.json" --report-md "$WORK/comparison.md"
   code=$?
   printf 'compare exit status: %s\n' "$code"

Do **not** pass ``--seed`` or ``--resamples`` to reference mode: there is no
bootstrap sampling in that method and overrides are rejected. For every manual
scenario, stop the fixture with Ctrl-C after inspecting evidence; remove only
the temporary directories you created when their evidence is no longer needed.
The notebook manages both forms of cleanup automatically.

Evidence: provenance, cohorts and decision
------------------------------------------------------------

``collect`` writes actual raw artifacts with timestamped series and source
identities. ``summarize`` verifies content hashes before retaining an eligible
scalar. ``compare`` checks policy hashes and metric fingerprints, unique source
run IDs and content hashes across both cohorts, and nonoverlapping source
intervals. The planned day-separated runs satisfy those structural gates. These
checks do not establish comparable hardware, cache state, traffic or causality.
An altered raw artifact is an input error, not valid comparison evidence.

For this higher-is-worse metric, the oriented effect is current mean minus
baseline mean: 0 seconds in pass and 10 seconds in regression. Cohort bootstrap
resamples **run-level values**, not the within-run timestamped observations.
There is one enabled gate, so nominal alpha 0.05 and Bonferroni effective alpha
0.05 agree. Seed 20260705 and 1000 requested resamples reproduce the ordered
calculation; the engine records 2000 effective resamples because of its floor.
The decision lower bound is the effective-alpha percentile of resampled
oriented mean differences. It is not a p-value, a posterior probability or a
guaranteed-coverage confidence interval.

The strict rule is ``FAIL`` exactly when the lower decision bound is **greater
than** the practical threshold. Equality is ``PASS``. Inspect these actual
fields in the JSON report, rather than treating the exit status alone as an
explanation:

.. list-table:: Expected synthetic evidence
   :header-rows: 1

   * - Selection
     - Baseline/current values (seconds)
     - Report evidence
     - Suite / CLI exit
   * - pass
     - [10, 10] / [10, 10]
     - effect 0, decision lower bound 0, threshold 0
     - PASS / 0
   * - regression
     - [10, 10] / [20, 20]
     - effect 10, decision lower bound 10, threshold 0
     - FAIL / 1
   * - advisory-reference
     - [10, 10] / [20]
     - reference quantile 10, effect 10, anomaly true; no decision bound
     - INCONCLUSIVE / 2

The reference quantile is the upper oriented baseline-tail quantile at
``1 - effective_alpha``. Its positive reference effect above threshold sets an
**advisory** anomaly; it never upgrades this metric to PASS or FAIL. Its seed
and resample fields are null. All scenarios retain a small-sample warning.
Reports spell the statuses in lowercase; the uppercase terms above name the
decision categories. Inadequate or incompatible evidence can also produce
INCONCLUSIVE; it must not be silently treated as PASS.

Repeat the identical compare command at existing report paths without
``--force`` to observe exit **3**, ``error: invalid command input``. This is
overwrite preflight, not a fourth statistical verdict. Lesson 05 captures that
handled failure while itself exiting successfully. CI must preserve the child
status and decide explicitly how FAIL, INCONCLUSIVE and input errors affect the
job. Retain both portable report formats in a real CI workflow.

Takeaway and follow-up investigation
------------------------------------

A PASS says only that this policy did not flag a bound above its threshold; it
does not prove equivalence or no user-visible slowdown. A FAIL identifies a
policy breach, not its cause. The noiseless two-run fixture cannot validate
coverage, false-alarm rates, independence or generalization to future workloads.
More bootstrap draws do not add independent experiments or repair biased data.

After a real FAIL, inspect exclusions and source provenance first, then compare
workload mix, deployment changes, hardware, saturation and cache/warmup state.
Use profiling or a controlled follow-up experiment to investigate candidate
causes; do not tune the threshold after seeing the outcome or rerun until PASS.
Plan representative independent runs and realistic warmup/cooldown in advance.

For the shorter guided entry point see :doc:`first-comparison`. For the rationale
continue with :doc:`../explanation/measurement-and-summaries`,
:doc:`../explanation/eligibility-and-comparability`,
:doc:`../explanation/uncertainty-and-comparison` and
:doc:`../explanation/decisions-and-limitations`. The executable labs 06-10 build
the statistical vocabulary and contrast educational methods without adding a
new production decision engine.
