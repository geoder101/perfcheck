Create a policy file
====================

Goal
----

Write a suite policy that ``perfcheck`` can collect, summarize, and compare
under. A policy is a self-describing JSON snapshot of the suite's metrics,
queries, eligibility rules, and comparison settings.

Prerequisite
------------

A Prometheus endpoint that exposes the metrics the suite measures, a unique
suite identifier, and one or more metrics each with a Prometheus query. Have the
CLI installed after ``just sync`` (or use the installed ``perfcheck`` directly
instead of ``just cli``). To install the tool once from the checkout root, run
``just install``. The root `README.md <https://github.com/geoder101/perfcheck/blob/main/README.md#install>`_ documents setup and prerequisites.

Steps
-----

#. Write a policy file with the required fields. The ``policy_sha256`` is a
   placeholder until the policy is stamped; a run of sixty-four zeros is fine.
   Point ``$schema`` at the hosted JSON Schema so your editor validates the file
   against the versioned contract.

   .. code-block:: json

      {
        "$schema": "https://raw.githubusercontent.com/geoder101/perfcheck/refs/heads/main/schemas/v1/perfcheck-policy.schema.json",
        "policy_sha256": "",
        "policy_id": "my-suite-policy",
        "suite_id": "my-suite",
        "metrics": [
          {
            "metric_id": "latency_ms",
            "query": "rate(http_request_duration_seconds_sum[1m])",
            "unit": "milliseconds",
            "direction": "higher_is_worse",
            "statistic": "p95",
            "practical_threshold": 0.05,
            "step_seconds": 10,
            "rate_window_seconds": 60
          }
        ]
      }

   The ``$schema`` pointer is a pure authoring aid: it lets editors validate the
   file against the hosted Schema and never affects validation or the policy
   content hash. It points at the publicly served Schema on the default branch,
   so it pins the exact major version and does not track patch or minor changes.
   ``perfcheck`` strips it before validation and preserves it verbatim when it
   stamps the policy.

#. Stamp the policy with its content hash so it can be used and verified. The
   command rewrites the file in canonical order, fills in ``policy_sha256`` and
   any default settings, and preserves the ``$schema`` pointer. It overwrites the
   input
   path in place, so pass ``--force`` to allow that.

   .. code-block:: console

      $ just cli policy stamp --input policy.json --output policy.json --force

#. Verify the stamped policy before collecting or comparing it.

   .. code-block:: console

      $ just cli policy check --input policy.json

Expected observable
-------------------

Stamping rewrites the policy and reports the destination. Checking prints
``policy my-suite-policy is valid (09515a29db08)`` and exits ``0``. A malformed
policy, a schema failure, or a content-hash mismatch exits ``3``. A ``$schema``
pointer to an unrecognized schema version prints a warning on stderr but
still exits ``0``.

Related material
----------------

Continue to :doc:`collect-a-run` to collect under the policy, :doc:`summarize-evidence`
and :doc:`compare-cohorts` to build and compare evidence, :doc:`../reference/policy-and-artifacts`
for the policy and artifact boundaries, and :doc:`../tutorials/first-comparison`
for a guided first comparison.
