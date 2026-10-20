"""Marimo Markdown output helpers."""

import marimo as mo


def md(text: str) -> None:
    """Replace the current output with rendered Markdown."""
    mo.output.replace(mo.md(text))
