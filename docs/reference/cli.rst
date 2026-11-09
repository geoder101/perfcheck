CLI reference
=============

Use the live help for the complete, installed command contract:

.. code-block:: console

   perfcheck --help
   perfcheck collect --help
   perfcheck summarize --help
   perfcheck compare --help

``collect``
-------------

``collect`` writes one portable raw-run artifact for every metric in a suite.
It requires ``--suite``, ``--run-id``, ``--start``, ``--end``, and ``--out``.
``--prometheus-url`` overrides the configured endpoint for this invocation.
If an enabled metric cannot be collected, the command still writes its raw
evidence and exits with status ``4``.

``summarize``
---------------

``summarize`` verifies one raw run and writes its canonical summary. It
requires ``--policy``, ``--run``, and ``--out``. Pass ``--force`` only to
replace an existing output path.

``compare``
-------------

``compare`` evaluates current and baseline evidence under one policy. It
requires ``--policy``, repeated ``--current`` inputs, repeated ``--baseline``
inputs, and at least one of ``--report-json`` or ``--report-md``; supply both
to write both formats. Only supplied report paths are checked and written.
It accepts raw runs as
convenience inputs and derives their summaries in memory; ``--write-summary-cache``
is the explicit opt-in for writing cache artifacts. ``--seed`` and
``--resamples`` override bootstrap settings, ``--json`` additionally emits the
JSON report to stdout (it does not replace a report-file option), and ``--force``
allows replacement of supplied report destinations. Omitting both report-file
options is an input error with exit status ``3``, even with ``--json``.

Exit outcomes
-------------

``compare`` exits ``0`` for ``PASS``, ``1`` for ``FAIL``, and ``2`` for
``INCONCLUSIVE``. Invalid command input and output-path contract failures exit
``3``. A collection with an enabled metric failure exits ``4``. An unexpected
boundary failure exits ``5`` and reports without its message.
