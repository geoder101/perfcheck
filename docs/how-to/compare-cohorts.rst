Compare current and baseline cohorts
====================================

Goal
----

Evaluate current and baseline evidence under one policy and write JSON,
Markdown, or both report formats.

Prerequisite
------------

Have a policy, at least one current input, at least one baseline input, and at
least one report destination (distinct paths when requesting both formats).
Inputs can be verified summaries or raw-run
convenience inputs for the same policy.

Run these commands from the source-checkout root after ``just sync``.
For an installed application, use ``perfcheck`` directly instead of ``just cli``.

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
