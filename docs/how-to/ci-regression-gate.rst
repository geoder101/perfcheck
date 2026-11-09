Use comparison outcomes in CI
=============================

Goal
----

Make a CI job distinguish a passing comparison, a regression, an inconclusive
result, and invalid command input.

Prerequisite
------------

Have a policy, current and baseline evidence, and two report destinations that
your CI job may write. Keep secrets out of command arguments and persisted
paths.

For source-checkout use, run from the checkout root after ``just sync``.
For an installed application, use ``perfcheck`` directly instead of
``uv run perfcheck``.

Steps
-----

#. Run ``compare`` with repeated cohort flags and persist both reports:

   Unlike ordinary how-to commands, this guide uses ``uv run perfcheck`` directly
   because CI classifies exact application exit statuses. The configured Windows
   ``powershell.exe -Command`` recipe shell can normalize native nonzero statuses,
   so ``just cli`` is not a portable exact-status interface.

   .. code-block:: console

      $ uv run perfcheck compare --policy policy.json --current summaries/current.json --baseline summaries/baseline.json --report-json reports/comparison.json --report-md reports/comparison.md

#. Configure the job outcome from the command's exit status, while retaining
   the JSON and Markdown reports for inspection.

Expected observable
-------------------

``compare`` returns exit status ``0`` for ``PASS``, exit status ``1`` for
``FAIL``, and exit status ``2`` for ``INCONCLUSIVE``. Exit status ``3`` means
invalid command input, such as an existing output without ``--force``. A
collection job can return exit status ``4`` after writing a raw run with an
enabled metric collection failure. The remaining command outcome is the
exit status ``5`` for ``internal failure``: an unexpected error crossed the
boundary and was reported without its message.

These application outcomes (``0`` through ``5``) are distinct from launcher or
recipe failures. If the application cannot start, inspect the launcher diagnostic;
that failure is not a statistical verdict.

Related material
----------------

Start with :doc:`../tutorials/first-comparison`, then use
:doc:`compare-cohorts` to build the report-producing command. See
:doc:`../reference/index` for complete CLI syntax and
:doc:`../explanation/decisions-and-limitations` for decision limits.
