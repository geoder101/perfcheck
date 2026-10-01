"""perfcheck console application."""

import typer

app = typer.Typer(help="Reproducible performance-regression evidence for CI.")


@app.callback()
def main() -> None:
    """Configure the perfcheck command group."""
