"""Sphinx configuration for the perfcheck theory curriculum."""

project = "perfcheck"
needs_sphinx = "9.1"
extensions: list[str] = []
nitpicky = True
exclude_patterns = ["_build"]

html_theme = "furo"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
