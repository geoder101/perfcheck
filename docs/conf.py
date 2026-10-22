"""Sphinx configuration for the perfcheck documentation."""

import re
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
extensions = ["autoapi.extension"]
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
    target = node["reftarget"]
    if target in _EXTERNAL_REFERENCES:
        return nodes.reference(
            "", "", content, refuri=_EXTERNAL_REFERENCES[target], internal=False
        )
    canonical = _BOOTSTRAP_REEXPORTS.get(target)
    if canonical:
        entry = env.domains.python_domain.objects.get(canonical)
        if entry:
            return make_refnode(
                app.builder, node["refdoc"], entry.docname, entry.node_id, content
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
    _ = app.connect("missing-reference", _resolve_reference)
    api_index = Path(app.srcdir) / "reference" / "api" / "index.rst"
    api_index.parent.mkdir(parents=True, exist_ok=True)
    _ = api_index.write_text(
        "Internal API reference\n"
        "======================\n\n"
        ".. toctree::\n"
        "   :maxdepth: 2\n\n"
        "   perfcheck/index\n",
        encoding="utf-8",
    )


html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
