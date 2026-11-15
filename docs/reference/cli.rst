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
It requires ``--policy``, ``--run-id``, ``--start``, ``--end``, and ``--out``.
``--prometheus-url`` overrides the configured endpoint for this invocation.

HTTP auth is resolved from four optional flags with the matching environment
variable as fallback, and a flag wins over its env var. No policy is involved.
``--prometheus-auth-scheme`` selects ``none``, ``bearer``, or ``basic``; the CLI
rejects any other value. ``--prometheus-bearer-token`` supplies a bearer token,
and ``--prometheus-auth-basic-user`` and ``--prometheus-auth-basic-password``
supply the two halves of basic auth. Setting only
``PERFCHECK_PROMETHEUS_BEARER_TOKEN`` still infers bearer auth. The resolved
scheme and header are forwarded to the transport only; the token and password
never reach the artifact, labels, provenance, logs, or CLI output. An
incomplete configuration (for example, ``basic`` with no password) fails with a
secret-free message and exit status ``3``.

Pass ``--force`` only to replace an existing output path.
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

``policy``
----------

The ``policy`` group helps authors and verifiers work with policy files. It
reads, validates, and re-writes policy JSON only; it never collects evidence or
writes a report. Both subcommands require ``--input``.

``policy check``
----------------

``policy check`` verifies that a policy parses and that its ``policy_sha256``
matches its canonical content. It exits ``0`` when the policy is valid and
``3`` for invalid JSON, a schema failure, or a content-hash mismatch. Use it
before ``collect`` or ``compare`` to fail fast on a malformed policy.

``policy stamp``
----------------

``policy stamp`` writes canonical JSON stamped with a correct ``policy_sha256``.
A policy written without a hash, or with a stale one, is re-validated and
re-stamped; the written form is then accepted by ``collect``, ``summarize``, and
``compare`` unchanged. By default ``stamp`` overwrites the ``--input`` file in
place; pass ``--force`` to allow the overwrite. ``--output`` writes a different
path and ``--stdout`` prints the stamped policy without writing a file.
``--stdout`` takes precedence over ``--output``.

An incomplete policy fails the same way with exit status ``3``.

Exit outcomes
-------------

``compare`` exits ``0`` for ``PASS``, ``1`` for ``FAIL``, and ``2`` for
``INCONCLUSIVE``. Invalid command input and output-path contract failures exit
``3``. A collection with an enabled metric failure exits ``4``. An unexpected
boundary failure exits ``5`` and reports without its message.
