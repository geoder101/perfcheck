Compare current and baseline cohorts
====================================

Goal
----

Evaluate current and baseline evidence under one policy and write JSON,
Markdown, or both report formats.

Prerequisite
------------

The command itself performs one input check: you must pass at least one current
path and at least one baseline path to ``--current`` and ``--baseline``, plus at
least one report destination (distinct paths when requesting both formats).
Those counts are not the eligibility minimums; whether a method is selected from
them depends on the comparison method, described below.

Inputs can be verified summaries or raw-run convenience inputs for the same
policy.

Cohort size and comparison method
---------------------------------

Passing one current path and one baseline path is the only input check the
command performs. Whether those inputs select a usable method depends on the
policy ``comparison_mode`` and, in ``auto`` mode, on the cohort sizes:

* **Cohort bootstrap** (``cohort_bootstrap``, or ``auto`` with more than one
  current run) is the only path that can yield ``PASS`` or ``FAIL``. It needs
  at least ``min_current_runs`` (default ``5``) current inputs and at least
  ``min_baseline_runs`` (default ``10``) baseline inputs.
* **Baseline reference** (``baseline_reference``, or ``auto`` with exactly one
  current run) is advisory. It needs exactly one current input and at least
  ``min_baseline_reference_runs`` (default ``10``) baseline inputs, and it
  always returns ``INCONCLUSIVE`` even when it records an anomaly.

These counts are policy fields, not command flags. Set ``min_current_runs``,
``min_baseline_runs``, or ``min_baseline_reference_runs`` in the policy to move
a threshold, and set ``comparison_mode`` to force a method; an explicit mode
still has to meet its own count. Shortfalls report ``INCONCLUSIVE`` with a
retained reason instead of failing the command. See
:doc:`../explanation/decisions-and-limitations` for method selection and
:doc:`../explanation/eligibility-and-comparability` for the upstream gates.

Run these commands from the source-checkout root after ``just sync``.
For an installed application, use ``perfcheck`` directly instead of ``just cli``.
To install the tool once from the checkout root, run ``just install``. The root `README.md <https://github.com/geoder101/perfcheck/blob/main/README.md#install>`_ documents setup and prerequisites.

Steps
-----

#. Repeat ``--current`` once for every current cohort member and ``--baseline``
   once for every baseline member.
#. Supply ``--report-json``, ``--report-md``, or both to write reports to new paths:

   .. code-block:: console

      $ just cli compare --policy policy.json --current summaries/current-1.json --current summaries/current-2.json --baseline summaries/baseline-1.json --baseline summaries/baseline-2.json --report-json reports/comparison.json --report-md reports/comparison.md

#. Add ``--json`` if you also want the JSON report on stdout. This does not
   replace the requirement for at least one report-file option.

   .. code-block:: console

      $ just cli compare --policy policy.json --current summaries/current-1.json --baseline summaries/baseline-1.json --report-md reports/comparison.md --json > reports/comparison.json

   This writes the Markdown report and captures JSON stdout separately;
   diagnostics remain on stderr. The shell manages ``>`` redirection, so the
   capture is not protected by perfcheck's ``--force`` overwrite checks or atomic
   report writes. Application comparison exit statuses remain ``0``/``1``/``2`` for
   ``PASS``/``FAIL``/``INCONCLUSIVE``.

#. To use raw-run inputs, pass their paths to the same repeated cohort options.
   Summaries are derived in memory. Add ``--write-summary-cache`` only when you
   intentionally want canonical sibling summary caches written. Add ``--force``
   only when replacing the requested existing report destinations is intentional.

Expected observable
-------------------

The command checks and writes only the supplied report destinations; omitted
formats create no files. Its suite verdict produces exit status
``0`` for ``PASS``, exit status ``1`` for ``FAIL``, and exit status ``2`` for
``INCONCLUSIVE``. Existing report destinations require ``--force`` for replacement.
Missing report outputs, duplicate destinations (even with ``--force``), and
other invalid command input return exit status ``3``.
These are application outcomes, not guaranteed ``just cli`` exit statuses.
For exact classification, follow :doc:`ci-regression-gate`; a launcher or recipe
failure is not a statistical verdict.

Related material
----------------

For the first guided flow, use :doc:`../tutorials/first-comparison`. See
:doc:`../reference/index` for complete comparison syntax and
:doc:`../explanation/uncertainty-and-comparison` for interpretation boundaries.
