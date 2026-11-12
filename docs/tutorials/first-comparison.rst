Your first comparison
=====================

Goal
----

Follow the supported ``collect`` -> ``summarize`` -> ``compare`` flow without
pointing at a live Prometheus service or choosing persistent output paths.

Prerequisite
------------

Native setup requires `Just <https://just.systems/man/en/>`_, `uv <https://docs.astral.sh/uv/>`_, and
`Python <https://www.python.org/>`_ (at least v3.14). These
commands run against a local copy of the repository, so work from the root of
your clone; see the project's `README.md <https://github.com/geoder101/perfcheck/blob/main/README.md>`_
for the clone command and full prerequisites:

.. code-block:: console

   $ just sync

This installs the locked dev/docs/examples groups, not just the minimal lesson
dependencies. The `curriculum index <https://github.com/geoder101/perfcheck/blob/main/examples/README.md>`_ explains
the authoring, interactive viewing, and noninteractive script recipes.

Steps
-----

#. Run the first five executable lessons in order. They use local fixtures and
   temporary workspaces, so they are the safe first comparison path.

    * `Lesson 01, workflow overview <https://github.com/geoder101/perfcheck/blob/main/examples/01-overview.py>`_
    * `Lesson 02, collect a raw run <https://github.com/geoder101/perfcheck/blob/main/examples/02-collect.py>`_
    * `Lesson 03, summarize evidence <https://github.com/geoder101/perfcheck/blob/main/examples/03-summarize.py>`_
    * `Lesson 04, compare cohorts <https://github.com/geoder101/perfcheck/blob/main/examples/04-compare.py>`_
    * `Lesson 05, CI outcomes <https://github.com/geoder101/perfcheck/blob/main/examples/05-failures-and-ci.py>`_

#. Start with the overview lesson:

   .. code-block:: console

      $ just notebook-run examples/01-overview.py

#. Continue through lesson 05. The lessons exercise the CLI, but they do not
   replace it. The supported public surface remains the ``perfcheck`` command.

Expected observable
-------------------

The lessons show one raw run becoming one verified summary, then current and
baseline summaries becoming JSON and Markdown reports. Lesson 05 demonstrates
how a nonzero result becomes a CI outcome.

Next steps
----------

Use :doc:`../how-to/collect-a-run` for a real collection task,
:doc:`../how-to/summarize-evidence` for verified input, and
:doc:`../how-to/compare-cohorts` for cohort evaluation. See
:doc:`../reference/index` for complete CLI syntax and
:doc:`../explanation/uncertainty-and-comparison` for the comparison rationale.
