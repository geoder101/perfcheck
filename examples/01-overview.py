import marimo  # noqa: D100, N999

__generated_with = "0.24.2"
app = marimo.App(width="medium")


@app.cell
def _():  # noqa: ANN202
    import marimo as mo  # noqa: PLC0415

    return (mo,)


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    # perfcheck overview

    ## Goal

    Learn the supported evidence flow: `collect` writes a portable raw run,
    `summarize` verifies that raw run and creates a canonical summary, and
    `compare` evaluates summaries under one policy.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Inputs

    This lesson uses only the supported `perfcheck --help` command. The CLI is
    the stable surface; internal Python APIs and artifact schemas can change.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    from pathlib import Path  # noqa: I001, PLC0415
    import sys  # noqa: PLC0415

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))
    from examples._support import (  # noqa: PLC0415
        perfcheck_executable,
        run_local_command,
    )

    return perfcheck_executable, repository_root, run_local_command


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(perfcheck_executable, repository_root, run_local_command):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    help_result = run_local_command(  # pyright: ignore[reportUnknownVariableType]
        (str(perfcheck_executable()), "--help"),  # pyright: ignore[reportUnknownArgumentType]
        cwd=repository_root,
    )
    supported_commands = tuple(
        command
        for command in ("collect", "summarize", "compare")
        if command in help_result.stdout  # pyright: ignore[reportUnknownMemberType]
    )
    return help_result, supported_commands  # pyright: ignore[reportUnknownVariableType]


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Run

    The command above invokes `perfcheck --help` through the project-local
    executable. It does not create evidence or contact a service.
    """
    )
    return  # noqa: PLR1711


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Evidence

    The narrowed excerpt below lists only the supported workflow commands from
    live help, so terminal wrapping and help styling do not distract from the
    stable learning point.
    """
    )
    return  # noqa: PLR1711


@app.cell  # pyright: ignore[reportUnknownArgumentType]
def _(help_result, supported_commands):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    evidence = "\n".join(f"- {command}" for command in supported_commands)  # pyright: ignore[reportUnknownVariableType]
    print("Goal: inspect the supported CLI flow")  # noqa: T201
    print("Inputs: perfcheck --help")  # noqa: T201
    print(f"Run: exit status {help_result.returncode}")  # noqa: T201  # pyright: ignore[reportUnknownMemberType]
    print(f"Evidence:\n{evidence}")  # noqa: T201
    return (evidence,)


@app.cell(hide_code=True)
def _(mo):  # noqa: ANN001, ANN202  # pyright: ignore[reportMissingParameterType, reportUnknownParameterType]
    mo.md(  # pyright: ignore[reportUnknownMemberType]
        """
    ## Takeaway

    Start every workflow through the CLI: collect raw evidence, summarize a
    verified raw run, then compare verified inputs under one policy.
    """
    )
    return  # noqa: PLR1711


@app.cell
def _():  # noqa: ANN202
    print("Takeaway: use collect -> summarize -> compare through perfcheck.")  # noqa: T201
    return  # noqa: PLR1711


if __name__ == "__main__":
    app.run()  # pyright: ignore[reportUnusedCallResult]
