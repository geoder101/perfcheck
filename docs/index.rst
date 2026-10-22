perfcheck documentation
=======================

``perfcheck`` produces reproducible performance-regression evidence for CI.
Its supported public surface is the ``perfcheck`` command-line interface.

The workflow turns metric observations into a policy decision:

#. ``collect`` writes one portable raw-run artifact from the configured suite.
#. ``summarize`` verifies that raw evidence and writes a canonical summary.
#. ``compare`` evaluates current and baseline evidence under one policy.

Choose the documentation path that fits your goal.

.. toctree::
   :maxdepth: 1
   :caption: Documentation paths

   tutorials/index
   how-to/index
   reference/index
   explanation/index
