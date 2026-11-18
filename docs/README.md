# Documentation repository guide

This guide is for readers browsing the checkout. The Sphinx site still starts
at [index.rst](index.rst); this README doesn't replace that entry point or join
the site's navigation. It needs no Markdown parser in Sphinx.

The supported public surface is the `perfcheck` CLI only. Internal Python APIs
and artifact schemas aren't compatibility promises. See the
[root scope statement](../README.md#scope).

## Find the right documentation

The site follows four [Diataxis-style](https://diataxis.fr/) paths:

| Index | Read it for |
| --- | --- |
| [Tutorials](tutorials/index.rst) | A guided first comparison and an artifact-to-CI case study. |
| [How-to guides](how-to/index.rst) | Task-focused collection, summarization, comparison, and CI steps. |
| [Reference](reference/index.rst) | CLI details, policy and artifact boundaries, glossary, and internal API navigation. |
| [Explanation](explanation/index.rst) | Statistical foundations, evidence interpretation, policy, and limitations. |

Choose a beginner, practitioner, or deep-dive route in
[Learning paths](explanation/learning-paths.rst). For executable lessons, use
the [Marimo curriculum index](../examples/README.md), which owns lesson order
and lesson setup instructions. Teaching models don't add production CLI methods.

## Authored inputs and generated outputs

- Authored `.rst` pages live here and in the four documentation paths above.
  Update their indexes when changing site navigation.
- [_static/](_static/) holds authored assets, including `custom.css` and images.
- [_templates/autoapi/](_templates/autoapi/) holds authored templates for
  generated internal API pages.
- [conf.py](conf.py) configures Furo, source-parsed AutoAPI, diagram and equation
  rendering, and reference resolution. AutoAPI reads all of [src/](../src/)
  without importing application modules; private and special members aren't
  included in its configured member options.
- `docs/reference/api/` is ignored generated RST, including its landing page.
  Don't edit it by hand. The authored Reference index owns its site navigation;
  these pages describe internals, not a supported public Python API.
- `docs/_build/` is ignored build output. HTML and rendered assets go under
  `docs/_build/html/`; neither output tree is an authored documentation source.

Mermaid diagrams and equations are rendered at build time to local SVG assets.
Their native build dependencies differ from what readers need: viewing those
assets doesn't require Node, Chrome, TeX, JavaScript, or a CDN connection.

## Build and preview from the repository root

Read the [root installation and rendering prerequisites](../README.md#install)
first, including the required Node/npm, browser libraries, LaTeX packages, and
`dvisvgm`. The [justfile](../justfile) is the command authority.

```bash
just docs-tools         # explicitly provision native JS tools and Chrome
just docs-check         # clean output, then build HTML with warnings as errors
just docs-preview       # fresh checked build, then serve on port 8000
just docs-preview 8765  # choose another port; stop the server with Ctrl-C
```

`just docs-tools` runs npm's locked install with scripts disabled, then explicitly
installs Puppeteer's Chrome. Run it for first native setup or documentation-tool
updates. Builds don't implicitly install JS tools or browsers.
`just docs-check` uses the optional docs dependency group and rebuilds without
cached renderer assets. `just docs-preview [port]` depends on that check before
serving `docs/_build/html`; stop preview processes when finished.

For the [optional Podman environment](../README.md#optional-podman-environment),
follow the root instructions instead: the image already provides the tools and
browser, so don't run `docs-tools` inside it. Don't run host and container builds
concurrently against the same `docs/_build/` output.

These commands describe local builds, not verified hosted deployment. The root
README owns the [hosting setup checklist](../README.md#one-time-github-hosting-setup-owner)
and pending platform validation.
