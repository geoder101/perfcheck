Authenticate Prometheus collection
==================================

Goal
----

Send authenticated HTTP requests to a Prometheus endpoint during collection
without letting the credential reach any artifact, log, or CLI output.

Prerequisite
------------

Have a suite policy that reaches the endpoint over HTTP(S), plus the
credentials the chosen scheme needs. HTTP auth is a runtime and CLI concern
only: the collection transport applies the header, and no policy, artifact,
label, provenance, or log carries the secret.

Run these commands from the source-checkout root after ``just sync``.
For an installed application, use ``perfcheck`` directly instead of ``just cli``.
To install the tool once from the checkout root, run ``just install``. The root `README.md <https://github.com/geoder101/perfcheck/blob/main/README.md#install>`_ documents setup and prerequisites.

Steps
-----

#. Pick a scheme. ``none`` sends no ``Authorization`` header, ``bearer`` sends
   ``Authorization: Bearer <token>``, and ``basic`` sends
   ``Authorization: Basic <base64(user:pass)>``. Choose it with
   ``--prometheus-auth-scheme`` (``none``, ``bearer``, or ``basic``); the CLI
   rejects any other value.
#. Supply the matching credential as a flag or through its environment
   variable. A flag wins over its env var.

   .. list-table:: Flags and environment variables
      :header-rows: 1
      :widths: 42 58

      * - Flag
        - Environment variable
      * - ``--prometheus-auth-scheme``
        - ``PERFCHECK_PROMETHEUS_AUTH_SCHEME``
      * - ``--prometheus-bearer-token``
        - ``PERFCHECK_PROMETHEUS_BEARER_TOKEN``
      * - ``--prometheus-auth-basic-user``
        - ``PERFCHECK_PROMETHEUS_BASIC_USERNAME``
      * - ``--prometheus-auth-basic-password``
        - ``PERFCHECK_PROMETHEUS_BASIC_PASSWORD``

#. For bearer auth, pass ``--prometheus-bearer-token`` (or set
   ``PERFCHECK_PROMETHEUS_BEARER_TOKEN``). Setting only that env var, with no
   flags, still works: the scheme is inferred as bearer.
#. For basic auth, pass both ``--prometheus-auth-basic-user`` and
   ``--prometheus-auth-basic-password`` (or set the matching env vars).
#. Run collection as usual, adding ``--prometheus-url`` if the suite policy
   needs an endpoint override for this invocation.

Expected observable
-------------------

On a complete collection, the command writes the raw-run artifact and reports
the run identifier. The resolved scheme and its header are forwarded to the
transport only; the token and password never appear in the artifact, labels,
provenance, logs, or CLI output. If the resolved configuration is incomplete
(for example, ``basic`` with no password), the command fails with a secret-free
message and exit status ``3``.

Related material
----------------

See :doc:`collect-a-run` for the collection workflow and
:doc:`../reference/cli` for the complete ``collect`` option list. The root
README's Prometheus authentication section summarizes the flags, scheme values,
and precedence.
