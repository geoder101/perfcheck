perfcheck documentation
=======================

``perfcheck`` produces reproducible performance-regression evidence for CI.
Its supported public surface is the ``perfcheck`` command-line interface.

The workflow turns metric observations into a policy decision:

#. ``collect`` writes one portable raw-run artifact from the configured suite.
#. ``summarize`` verifies that raw evidence and writes a canonical summary.
#. ``compare`` evaluates current and baseline evidence under one policy.

Welcome! Start with :doc:`explanation/learning-paths` to choose a beginner,
practitioner, or deep-dive route through the existing guides and executable labs.
For a quick first run, use :doc:`tutorials/first-comparison`; for a complete
artifact-to-CI walkthrough, use :doc:`tutorials/performance-verification-case-study`.
The statistical teaching models explain assumptions without adding CLI methods.

Documentation and lessons keep educational content in this repository, with no
required runtime fetches from external HTTP servers or hosted chart services.
Install the dependencies and build tools first (including LaTeX with AMS/preview
and ``dvisvgm`` for documentation equations); local preview servers and loopback
lesson fixtures are supported. External citations are optional links, not
embedded resources, and require a connection only if you choose to follow them.

Choose the documentation path that fits your goal.

.. toctree::
   :maxdepth: 1
   :caption: Documentation paths

   tutorials/index
   how-to/index
   reference/index
   explanation/index
