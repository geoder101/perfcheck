# pyright: basic
# ruff: noqa: ANN001, ANN202, D100, I001, N999, PLC0415, PLR1711, T201

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo

    return (mo,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    # perfcheck overview

    ## Goal

    Learn the supported evidence flow: `collect` writes a portable raw run,
    `summarize` verifies that raw run and creates a canonical summary, and
    `compare` evaluates summaries under one policy.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Inputs

    This lesson uses only the supported `perfcheck --help` command. The CLI is
    the stable surface; internal Python APIs and artifact schemas can change.
    """)
    return


@app.cell
def _():
    from pathlib import Path
    import sys

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))
    from examples._support import perfcheck_executable, run_local_command

    return perfcheck_executable, repository_root, run_local_command


@app.cell
def _(perfcheck_executable, repository_root, run_local_command):
    help_result = run_local_command(
        (str(perfcheck_executable()), "--help"), cwd=repository_root
    )
    supported_commands = tuple(
        command
        for command in ("collect", "summarize", "compare")
        if command in help_result.stdout
    )
    return help_result, supported_commands


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Run

    The command above invokes `perfcheck --help` through the project-local
    executable. It does not create evidence or contact a service.
    """)
    return


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Evidence

    The narrowed excerpt below lists only the supported workflow commands from
    live help, so terminal wrapping and help styling do not distract from the
    stable learning point.
    """)
    return


@app.cell
def _(help_result, supported_commands):
    evidence = "\n".join(f"- {command}" for command in supported_commands)
    print("Goal: inspect the supported CLI flow")
    print("Inputs: perfcheck --help")
    print(f"Run: exit status {help_result.returncode}")
    print(f"Evidence:\n{evidence}")
    return (evidence,)


@app.cell(hide_code=True)
def _(mo):
    mo.md("""
    ## Takeaway

    Start every workflow through the CLI: collect raw evidence, summarize a
    verified raw run, then compare verified inputs under one policy.
    """)
    return


@app.cell
def _():
    print("Takeaway: use collect -> summarize -> compare through perfcheck.")
    return


if __name__ == "__main__":
    app.run()
