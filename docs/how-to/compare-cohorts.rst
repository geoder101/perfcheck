Compare current and baseline cohorts
====================================

Goal
----

Evaluate current and baseline evidence under one policy and write both report
formats.

Prerequisite
------------

Have a policy, at least one current input, at least one baseline input, and two
distinct report destinations. Inputs can be verified summaries or raw-run
convenience inputs for the same policy.

Steps
-----

#. Repeat ``--current`` once for every current cohort member and ``--baseline``
   once for every baseline member.
#. Write JSON and Markdown reports to new paths:

   .. code-block:: console

      $ uv run perfcheck compare --policy policy.json --current summaries/current-1.json --current summaries/current-2.json --baseline summaries/baseline-1.json --baseline summaries/baseline-2.json --report-json reports/comparison.json --report-md reports/comparison.md

#. To use raw-run inputs, pass their paths to the same repeated cohort options.
   Summaries are derived in memory. Add ``--write-summary-cache`` only when you
   intentionally want canonical sibling summary caches written. Add ``--force``
   only when replacing both existing report destinations is intentional.

Expected observable
-------------------

The command writes both report formats. Its suite verdict produces exit status
``0`` for ``PASS``, exit status ``1`` for ``FAIL``, and exit status ``2`` for
``INCONCLUSIVE``. Existing report destinations, duplicate destinations, and
other invalid command input return exit status ``3`` unless replacement was
explicitly enabled with ``--force``.

Related material
----------------

For the first guided flow, use :doc:`../tutorials/first-comparison`. See
:doc:`../reference/index` for complete comparison syntax and
:doc:`../explanation/uncertainty-and-comparison` for interpretation boundaries.
