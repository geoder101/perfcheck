Upgrade Python dependencies
===========================

Goal and scope
--------------

Upgrade the runtime dependencies and all uv dependency groups: ``dev``, ``docs``,
``examples``, and optional ``mutation``. Review the ``uv_build`` build backend
separately. Keep the declared Python range ``>=3.14,<3.15`` unchanged.
Upgrades of the uv executable, npm tools, OS packages, and container images are
separate tasks, not steps in this procedure.

Prepare the checkout
--------------------

Run commands from the repository root with the existing contributor tools and
documentation rendering prerequisites available. Inspect the working tree,
staged changes, and existing ``pyproject.toml`` and ``uv.lock`` diffs first.
Preserve other work, including dependency edits already in progress; don't reset
files or overwrite staging to get a clean baseline. Record any known baseline
check failures so you can distinguish them from upgrade-induced failures.

Look up current stable candidates in official PyPI package metadata or upstream
release listings, then read their release notes and Python/platform requirements.
Choose stable compatible releases, not prereleases or automatically every newest
release. Check changes affecting CLI behavior, numerical results, validation,
lint/type rules, documentation extensions, and executable lessons.

Update constraints and resolve
------------------------------

#. Review ``[project].dependencies`` and every ``[dependency-groups]`` entry in
   ``pyproject.toml``. Intentionally update exact pins and upper bounds where a
   reviewed candidate requires it. Retain justified compatibility limits and
   the mutation group's Windows exclusion marker.

   Permissive lower bounds needn't rise just because the lockfile selects newer
   versions. Raising the minimum supported version is a separate intentional
   decision.

#. Review ``[build-system].requires`` separately and intentionally update its
   ``uv_build`` constraint when appropriate. Isolated build requirements aren't
   necessarily represented in ``uv.lock``; a lockfile refresh alone doesn't
   upgrade or verify the backend.

#. Refresh the complete lockfile:

   .. code-block:: console

      $ uv lock --upgrade

   This direct uv command is a maintenance exception because no Just recipe
   covers upgrades. It reconsiders locked versions within the declared
   constraints; it doesn't bypass pins, upper bounds, or compatibility rules.
   Resolution includes groups that aren't installed in the ordinary environment.

#. Review the ``pyproject.toml`` and ``uv.lock`` diff together. Check direct and
   transitive changes, artifact hashes, package sources, group membership, and
   Python/platform-specific branches. Keep credentials out of persisted files
   and diagnostics, following the existing repository policy.

   If a transitive dependency stays held back, investigate its parent's
   constraint and release notes rather than forcing an incompatible version.
   Explain deliberate holds and unexpected source or platform changes before
   accepting the resolution.

Install and check the ordinary groups
-------------------------------------

.. code-block:: console

   $ just sync

This verifies the lockfile and installs the locked runtime plus
``dev``/``docs``/``examples`` groups, excluding optional mutation tooling.
Don't treat successful resolution or installation as proof of compatibility.

Check optional mutation tooling without a campaign
--------------------------------------------------

On a supported Unix platform, check the optional group too. Its ``mutmut``
requirement excludes Windows; don't claim native Windows mutation support.
Inspect ``[tool.mutmut]`` and the repository's mutation helpers against upstream
configuration changes before probing the installed tooling.

.. code-block:: console

   $ uv sync --locked --group dev --group docs --group examples --group mutation
   $ uv run --locked --no-sync python -c "from importlib.metadata import version; import mutmut; print(version('mutmut'))"
   $ just sync

The probe checks the installed version and import, not mutation outcomes.
Review the configured options for compatibility; don't start ``just mutation``
merely to validate a dependency upgrade. Leave existing ``mutation/`` evidence
untouched. Always run the final ``just sync`` to restore the ordinary environment,
even if the optional install or probe fails. Run it as a separate cleanup step,
not chained behind a successful probe. Diagnose failures before proceeding.

Run the complete quality gate
-----------------------------

.. code-block:: console

   $ just check

This runs lock verification, formatting, lint, strict type checking, tests,
executable examples, strict documentation, and source/wheel builds. The final
``just build`` stage checks the separately declared build backend.
Ordinary checks remain coverage-free and mutation-free.

For each failure, determine whether the dependency change introduced it or
whether it was already present in the baseline. Neither category is a pass.
Make scoped compatibility fixes and add behavior regression tests when behavior
changes; don't add version-only snapshots or suppress errors to make checks green.
Re-run the affected checks and then the complete gate after fixing failures.

If ``just check`` stops early, later stages haven't passed. Run these separately
to diagnose those stages, with rendering prerequisites already provisioned:

.. code-block:: console

   $ just examples-check
   $ just docs-check
   $ just build

Serialize builds that share output directories, including host/container runs.
Passing a diagnostic stage doesn't make an incomplete ``just check`` green.

Review the result
-----------------

Keep the intentional constraint edits, reviewed lockfile changes, and necessary
compatibility fixes together for review without mixing unrelated work. Summarize
changed dependency areas, deliberate holds, checks run, and unresolved failures.
Report unrun platform or hosted checks as pending, not verified.

For application behavior boundaries, see :doc:`../reference/index` and
:doc:`../explanation/decisions-and-limitations`.
