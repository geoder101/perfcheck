Collect a raw run
=================

Goal
----

Collect every metric in a suite into one portable raw-run artifact.

Prerequisite
------------

Have a suite policy file, a unique run identifier, a UTC start and end time,
and a destination path that does not already exist. Use a credential-free
Prometheus base URL if the suite policy needs an override.

Run these commands from the source-checkout root after ``just sync``.
For an installed application, use ``perfcheck`` directly instead of ``just cli``.

Steps
-----

#. Choose a new output path. ``collect`` never overwrites an existing path.
#. Run collection with the required suite, interval, identifier, and output:

   .. code-block:: console

      $ just cli collect --suite policy.json --run-id run-2026-07-03 --start 2026-07-03T10:00:00Z --end 2026-07-03T10:10:00Z --out runs/run-2026-07-03.json

#. When the suite policy should be overridden for this invocation, add the
   documented ``--prometheus-url`` option with its safe HTTP(S) base URL.

Expected observable
-------------------

On a complete collection, the command writes the requested raw-run artifact
and reports the run identifier. If an enabled metric cannot be collected, it
still writes the raw run with the failure evidence and returns exit status
``4``. The command uses exit status ``3`` for invalid command input.
These are application outcomes; see :doc:`ci-regression-gate` when classifying
exact exit statuses rather than recipe success or failure.

Related material
----------------

Learn the safe sequence in :doc:`../tutorials/first-comparison`. See
:doc:`../reference/index` for complete collection syntax and
:doc:`../explanation/eligibility-and-comparability` for why collected evidence
may later be unsuitable for comparison.
