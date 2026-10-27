"""Sphinx configuration for the perfcheck documentation."""

import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from docutils import nodes
from sphinx.util.nodes import make_refnode

if TYPE_CHECKING:
    from jinja2 import Environment
    from sphinx.addnodes import pending_xref
    from sphinx.application import Sphinx
    from sphinx.environment import BuildEnvironment

project = "perfcheck"
needs_sphinx = "9.1"
extensions = [
    "autoapi.extension",
    "sphinx.ext.imgmath",
    "sphinxcontrib.mermaid",
]
imgmath_image_format = "svg"
imgmath_use_preview = True
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
mermaid_cmd = [sys.executable, str(_PROJECT_ROOT / "tools/mermaid.py")]
mermaid_cmd_shell = False
mermaid_output_format = "svg"
mermaid_params = ["--no-font-embed"]
mermaid_d3_zoom = False
mermaid_fullscreen = False
mermaid_config = {
    "theme": "base",
    "htmlLabels": False,
    "fontFamily": "system-ui, sans-serif",
    "themeVariables": {
        "fontFamily": "system-ui, sans-serif",
        "fontSize": "16px",
        "background": "#ffffff",
        "primaryColor": "#eff6ff",
        "primaryTextColor": "#1f2937",
        "primaryBorderColor": "#1d4ed8",
        "secondaryColor": "#ffffff",
        "tertiaryColor": "#eff6ff",
        "lineColor": "#1d4ed8",
        "edgeLabelBackground": "#ffffff",
    },
    "flowchart": {"htmlLabels": False, "rankSpacing": 24, "padding": 12},
}
nitpicky = True
exclude_patterns = ["_build", "_templates"]

autoapi_dirs = ["../src"]
autoapi_root = "reference/api"
autoapi_keep_files = True
autoapi_add_toctree_entry = False
autoapi_template_dir = "_templates/autoapi"
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]

# Exact destinations keep builds offline without accepting unknown Python names.
_EXTERNAL_REFERENCES = {
    "collections.abc.Mapping": "https://docs.python.org/3.14/library/collections.abc.html#collections.abc.Mapping",
    "collections.abc.Sequence": "https://docs.python.org/3.14/library/collections.abc.html#collections.abc.Sequence",
    "datetime.datetime": "https://docs.python.org/3.14/library/datetime.html#datetime.datetime",
    "enum.StrEnum": "https://docs.python.org/3.14/library/enum.html#enum.StrEnum",
    "pathlib.Path": "https://docs.python.org/3.14/library/pathlib.html#pathlib.Path",
    "numpy.typing.NDArray": "https://numpy.org/doc/stable/reference/typing.html#numpy.typing.NDArray",
    "numpy.float64": "https://numpy.org/doc/stable/reference/arrays.scalars.html#numpy.float64",
    "pydantic.TypeAdapter": "https://docs.pydantic.dev/latest/api/type_adapter/#pydantic.type_adapter.TypeAdapter",
    "pydantic.AwareDatetime": "https://docs.pydantic.dev/latest/api/types/#pydantic.types.AwareDatetime",
    "pydantic.BaseModel": "https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel",
    "pydantic.ConfigDict": "https://docs.pydantic.dev/latest/api/config/#pydantic.config.ConfigDict",
    "pydantic.RootModel": "https://docs.pydantic.dev/latest/api/root_model/#pydantic.root_model.RootModel",
    "pydantic.JsonValue": "https://docs.pydantic.dev/latest/api/types/#pydantic.types.JsonValue",
    "typer.Option": "https://typer.tiangolo.com/tutorial/options/",
    "httpx2.AsyncClient": "https://github.com/pydantic/httpx2",
    "httpx2.Response": "https://github.com/pydantic/httpx2",
}
_BOOTSTRAP_REEXPORTS = {
    f"perfcheck.bootstrap.{name}": f"perfcheck.bootstrap_models.{name}"
    for name in (
        "CohortBootstrapOptions",
        "BaselineReferenceResult",
        "CohortBootstrapResult",
        "RunValue",
    )
}


def _resolve_reference(
    app: Sphinx,
    env: BuildEnvironment,
    node: pending_xref,
    content: nodes.Element,
) -> nodes.reference | None:
    """Resolve only known dependencies and source-parsed bootstrap re-exports."""
    if node.get("refdomain") != "py":
        return None
    target = f"{node['reftarget']}"
    if target in _EXTERNAL_REFERENCES:
        return nodes.reference(
            "", "", content, refuri=_EXTERNAL_REFERENCES[target], internal=False
        )
    canonical = _BOOTSTRAP_REEXPORTS.get(target)
    if canonical:
        entry = env.domains.python_domain.objects.get(canonical)
        if entry:
            return make_refnode(
                app.builder, f"{node['refdoc']}", entry.docname, entry.node_id, content
            )
    return None


def _link_bases(value: str) -> str:
    """Split generic and union punctuation before linking individual base types."""
    return r"\ ".join(
        rf"\{part}" if part in "[],|" else f":py:obj:`{part.strip()}`"
        for part in re.split(r"([\[\],|])", value)
        if part.strip()
    )


def autoapi_prepare_jinja_env(env: Environment) -> None:
    """Handle union operands that AutoAPI 3.8's base-type filter leaves joined."""
    env.filters["link_bases"] = _link_bases


def setup(app: Sphinx) -> None:
    """Register the generated API landing page before Sphinx reads sources."""
    # Mermaid 2.1.1 supports argv lists and booleans but registers string defaults.
    for name, default, types in (
        ("mermaid_cmd", "mmdc", (str, list)),
        ("mermaid_cmd_shell", "False", (str, bool)),
    ):
        del app.config.values[name]
        app.add_config_value(name, default, "html", types=types)
    _ = app.connect("missing-reference", _resolve_reference)
    api_index = Path(app.srcdir) / "reference" / "api" / "index.rst"
    api_index.parent.mkdir(parents=True, exist_ok=True)
    _ = api_index.write_text(
        """Internal API reference
======================

.. toctree::
   :maxdepth: 2

   perfcheck/index
""",
        encoding="utf-8",
    )


html_theme = "furo"
html_title = project
html_static_path = ["_static"]
html_css_files = ["custom.css"]
