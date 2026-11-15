Policy and artifact boundaries
==============================

Policy
------

A suite policy defines its metrics, collection queries, eligibility rules,
comparison direction, thresholds, and bootstrap settings. Commands parse the
policy JSON before use and verify its ``policy_sha256`` against the canonical
policy content. Evidence from a different policy hash cannot be summarized or
compared under the selected policy.

A policy may carry a top-level ``$schema`` property that points at the hosted,
versioned JSON Schema in ``schemas/``. It is a pure authoring aid: perfcheck
strips it before validation, so it never blocks validation and never affects
``policy_content_sha256`` or policy identity. ``stamp`` preserves a present
``$schema`` verbatim, and ``policy check`` WARNS (without changing the exit
status) when the pointer references an unknown or older schema version.

Raw-run artifact
----------------

``collect`` writes a raw-run artifact with the suite policy snapshot, source
interval, per-metric collection evidence, and a content hash. A metric may be
available with a collected series or unavailable with collection-failure
evidence; the run remains portable evidence for both cases.

Summary artifact
----------------

``summarize`` accepts a verified raw run and creates a deterministic summary
artifact. Its content hash and source-run hash bind the summary to its input;
it records metric availability, eligibility evidence, and selected scalar
summaries. A summary is accepted by ``compare`` only when its content and
policy hashes verify and it is compatible with the selected policy.

Reports
-------

``compare`` writes one JSON report and one Markdown report. Their suite status
is ``PASS``, ``FAIL``, or ``INCONCLUSIVE``; the command status follows the
exit outcomes in :doc:`cli`.
