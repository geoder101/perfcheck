"""Introduce the supported perfcheck CLI evidence workflow."""

import marimo

__generated_with = "0.24.2"
app = marimo.App(width="medium")


with app.setup:
    import sys
    from pathlib import Path

    repository_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repository_root))

    from examples._markdown import md
    from examples._support import LessonContext, lesson_context, run_local_command


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
# perfcheck overview

## Goal

Learn the supported evidence flow: `collect` writes a portable raw run,
`summarize` verifies that raw run and creates a canonical summary, and
`compare` evaluates summaries under one policy.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Inputs

This lesson uses only the supported `perfcheck --help` command. The CLI is
the stable surface; internal Python APIs and artifact schemas can change.
        """)


@app.cell
def _() -> tuple[LessonContext]:
    context = lesson_context()
    return (context,)


@app.cell
def _(context: LessonContext) -> tuple[int, tuple[str, ...]]:
    help_result = run_local_command(
        (str(context.executable), "--help"),
        cwd=context.repository_root,
    )
    help_status = help_result.returncode
    supported_commands = tuple(
        command
        for command in ("collect", "summarize", "compare")
        if command in help_result.stdout
    )
    return help_status, supported_commands


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Run

The command above invokes `perfcheck --help` through the project-local
executable. It does not create evidence or contact a service.
        """)


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Evidence

The narrowed excerpt below lists only the supported workflow commands from
live help, so terminal wrapping and help styling do not distract from the
stable learning point.
        """)


@app.cell
def _(help_status: int, supported_commands: tuple[str, ...]) -> None:
    evidence = "\n".join(f"- {command}" for command in supported_commands)
    message = "\n".join(
        (
            "Goal: inspect the supported CLI flow",
            "Inputs: perfcheck --help",
            f"Run: exit status {help_status}",
            f"Evidence:\n{evidence}",
        )
    )
    _ = sys.stdout.write(f"{message}\n")


@app.cell(hide_code=True)
def _() -> None:
    md(r"""
## Takeaway

Start every workflow through the CLI: collect raw evidence, summarize a
verified raw run, then compare verified inputs under one policy.
        """)


@app.cell
def _() -> None:
    _ = sys.stdout.write(
        "Takeaway: use collect -> summarize -> compare through perfcheck.\n"
    )


if __name__ == "__main__":
    _app_run_result = app.run()
