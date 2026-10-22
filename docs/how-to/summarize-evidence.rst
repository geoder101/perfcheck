Summarize verified evidence
===========================

Goal
----

Create one canonical summary from one verified raw-run artifact.

Prerequisite
------------

Have the policy used for collection, a raw-run path, and a new summary output
path. If the output path already exists, decide whether replacing it is
intentional.

Steps
-----

#. Write the summary to a new destination:

   .. code-block:: console

      $ uv run perfcheck summarize --policy policy.json --run runs/run-2026-07-03.json --out summaries/run-2026-07-03.json

#. To intentionally replace an existing summary destination, repeat the same
   command with ``--force``.

Expected observable
-------------------

The command verifies the raw evidence before writing a canonical summary and
reports the summary identifier. Existing output paths are rejected unless
``--force`` is present. Invalid command input returns exit status ``3``.

Related material
----------------

The guided version is :doc:`../tutorials/first-comparison`. Consult
:doc:`../reference/index` for complete syntax and
:doc:`../explanation/measurement-and-summaries` for the summary calculations
and eligibility boundaries.
