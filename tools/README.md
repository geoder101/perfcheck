# Repository helpers

This directory supports repository checks, evidence handling, documentation
rendering, and container forwarding. These helpers aren't a supported application
API. The `perfcheck` CLI is the only supported public surface; start with the
[root README](../README.md) for the application workflow or the
[curriculum index](../examples/README.md) for executable lessons.

Run commands below from the repository root. The [justfile](../justfile) owns
the canonical recipes. `just sync` restores the ordinary locked development
environment; `just check` runs the standard gates. Neither `just check` nor
`just test` runs coverage or mutation.

For Python dependency maintenance, follow
[Upgrade Python dependencies](https://geoder101.github.io/perfcheck/how-to/upgrade-dependencies.html), including
all uv groups, the separate build backend, and compatibility checks.

## Coverage and CI evidence

- [coverage_gate.py](coverage_gate.py) clears owned reports and runs the fixed
  full-suite combined statement/branch coverage gate. It accepts no arguments.
- [quality_evidence.py](quality_evidence.py) captures invocation provenance and
  exports validated CI evidence. Its `quality_evidence_*` companions handle
  models, report reconciliation, and local HTML validation.

```bash
just coverage
just coverage tests/test_cli_compare.py
just coverage-check
```

`coverage` is exploratory, with optional pytest arguments and no default floor.
`coverage-check` requires fresh evidence and enforces the 99% combined gate.
Local outputs live under `coverage/`: `html/index.html`, `coverage.json`, and
hidden raw `.coverage` data. CI staging adds provenance, not an application
artifact. See [Coverage evidence](../README.md#coverage-evidence) for scope,
exclusions, failed-gate interpretation, and downloadable evidence.

## Optional mutation pilot and evidence

- [mutation_runner.py](mutation_runner.py) orchestrates the isolated Unix-only
  aggregation pilot without changing checkout sources.
- [mutation_campaign.py](mutation_campaign.py) runs its selected campaign;
  [mutation_evidence.py](mutation_evidence.py) reconciles outcomes and imports.
- [mutation_summary.py](mutation_summary.py) validates CI receipts, while
  [mutation_ci_artifacts.py](mutation_ci_artifacts.py) stages approved downloads.

```bash
just mutation
just sync
```

`mutation` explicitly installs its optional dependency group. Run `sync`
afterward to restore the ordinary environment without mutation tooling.
The pilot refuses nonempty `mutation/` output. Before running it, follow the
[preservation instructions](../README.md#optional-mutation-pilot) for existing
evidence. That section also explains `status.json`, logs, import receipts,
saved diffs, and why surviving mutants are advisory rather than a score gate.

## Mermaid and locked documentation assets

- [mermaid.py](mermaid.py) is Sphinx's shell-free launcher for an existing
  Mermaid renderer, using the selected Puppeteer browser profile.
- [docs/package.json](docs/package.json) declares the documentation-only JS tools;
  [docs/package-lock.json](docs/package-lock.json) locks their dependency tree.
- [docs/puppeteer-nosandbox.json](docs/puppeteer-nosandbox.json) configures native
   browser launches. Container profiles live alongside it and are selected by the
   launcher.

```bash
just docs-tools
just docs-check
just docs-preview
```

`docs-tools` is explicit native provisioning: it installs the locked npm tree
with lifecycle scripts disabled, then explicitly installs Puppeteer's Chrome.
The launcher and documentation build never install JS tools or browsers
implicitly. `docs-check` cleans and rebuilds strict HTML with local SVG assets;
`docs-preview` builds first, then serves it locally. The container image is
already provisioned, so don't run `docs-tools` there. Read the
[root setup guide](../README.md#install) for native prerequisites, renderer
selection, equation tools, and browser requirements rather than treating these
helpers as an installer API.

## Pages artifact validation

[pages_authorization.py](pages_authorization.py) checks the staged documentation
HTML tree, rejecting escaping paths, symlinks, and invalid local resource links.
It doesn't authorize deployment events; that authorization stays in Actions.
Pages publishes documentation only, never coverage or mutation evidence.
See the [owner checklist](../README.md#one-time-github-hosting-setup-owner) for
deployment restrictions and the hosted checks still requiring real runs.

## Podman adapters

[podman.sh](podman.sh) and [podman.ps1](podman.ps1) implement platform forwarding
for [podman.just](../podman.just), not a second set of project recipes.

```bash
just -f podman.just build
just -f podman.just run sync
just -f podman.just run check
just -f podman.just preview
```

The root `justfile` remains authoritative inside the container. Consult
[Optional Podman environment](../README.md#optional-podman-environment) for
source/state overrides, shared-output safety, sandbox policy, cleanup, and
platform limits. This map makes no container or hosted verification claim.
