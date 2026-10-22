Your first comparison
=====================

Goal
----

Follow the supported ``collect`` -> ``summarize`` -> ``compare`` flow without
pointing at a live Prometheus service or choosing persistent output paths.

Prerequisite
------------

From the repository root, install the optional lesson tools:

.. code-block:: console

   $ uv sync --group examples

Steps
-----

#. Run the first five executable lessons in order. They use local fixtures and
   temporary workspaces, so they are the safe first comparison path.

   * :download:`Lesson 01, workflow overview <../../examples/01-overview.py>`
   * :download:`Lesson 02, collect a raw run <../../examples/02-collect.py>`
   * :download:`Lesson 03, summarize evidence <../../examples/03-summarize.py>`
   * :download:`Lesson 04, compare cohorts <../../examples/04-compare.py>`
   * :download:`Lesson 05, CI outcomes <../../examples/05-failures-and-ci.py>`

#. Start with the overview lesson:

   .. code-block:: console

      $ uv run --group examples marimo run examples/01-overview.py

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
