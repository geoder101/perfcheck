import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]


class ShellRequest(Protocol):
    @property
    def param(self) -> str: ...


class RecipeRequest(Protocol):
    @property
    def param(self) -> tuple[str, tuple[str, ...]]: ...


@pytest.fixture(
    params=[
        pytest.param(
            ("notebook-run", ("run", "--group", "examples", "marimo", "run")),
            id="notebook-run",
        ),
        pytest.param(
            ("notebook-edit", ("run", "--group", "examples", "marimo", "edit")),
            id="notebook-edit",
        ),
        pytest.param(
            (
                "notebook-script",
                ("--directory", ".", "run", "--group", "examples", "python"),
            ),
            id="notebook-script",
        ),
    ]
)
def notebook_recipe(request: RecipeRequest) -> tuple[str, tuple[str, ...]]:
    return request.param


@dataclass(frozen=True, slots=True)
class NotebookHost:
    root: Path
    env: dict[str, str]
    recipe: str
    argv_prefix: tuple[str, ...]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        just = shutil.which("just")
        assert just
        return subprocess.run(  # noqa: S603
            [just, "--justfile", str(self.root / "justfile"), self.recipe, *args],
            cwd=self.root,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def argv(self) -> list[str]:
        return (self.root / "argv").read_bytes().decode().split("\0")[:-1]


@pytest.fixture(params=["sh", "pwsh"])
def notebook_host(
    tmp_path: Path,
    request: ShellRequest,
    notebook_recipe: tuple[str, tuple[str, ...]],
) -> NotebookHost:
    if sys.platform != "linux" or not shutil.which("just"):
        pytest.skip("fake executable harness requires Linux and host Just")
    powershell = request.param == "pwsh"
    if powershell and not shutil.which("pwsh"):
        pytest.skip("PowerShell 7 unavailable (Windows 5.1 is not tested here)")
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    justfile = (ROOT / "justfile").read_text()
    if powershell:
        # Exercise Windows recipes on the available Unix PowerShell host.
        justfile = justfile.replace("[unix]", "[swap]")
        justfile = justfile.replace("[windows]", "[unix]")
        justfile = justfile.replace("[swap]", "[windows]")
        justfile = justfile.replace("powershell.exe", "pwsh")
    _ = (root / "justfile").write_text(justfile)
    binary = tmp_path / "bin"
    binary.mkdir()
    fake = binary / "uv"
    _ = fake.write_text(
        r"""#!/bin/sh
printf '%s\0' "$@" > "$RECEIPT"
exit "${FAKE_STATUS:-0}"
"""
    )
    fake.chmod(0o755)
    env = {**os.environ, "FAKE_STATUS": "0", "RECEIPT": str(root / "argv")}
    env["PATH"] = f"{binary}:{env['PATH']}"
    recipe, argv_prefix = notebook_recipe
    return NotebookHost(root, env, recipe, argv_prefix)


@pytest.mark.parametrize(
    "notebook",
    [
        "examples/05-failures-and-ci.py",
        "examples/notebook with spaces.py",
        "examples/$(touch sentinel); &|<>$`'{}*?\".py",
    ],
)
def test_notebook_path_is_forwarded_literally(
    notebook_host: NotebookHost, notebook: str
) -> None:
    # Given: one notebook path, including shell-sensitive characters.
    # When: the real Just recipe invokes a recording uv executable.
    result = notebook_host.run(notebook)
    # Then: uv receives the fixed command and exactly one literal path.
    assert result.returncode == 0, result.stderr
    assert notebook_host.argv() == [*notebook_host.argv_prefix, notebook]
    assert not (notebook_host.root / "sentinel").exists()


@pytest.mark.parametrize(
    ("args", "diagnostic"),
    [((), "takes 1"), (("lesson.py", "extra.py"), "extra.py")],
)
def test_notebook_requires_one_argument(
    notebook_host: NotebookHost, args: tuple[str, ...], diagnostic: str
) -> None:
    # Given: a missing path or an extra positional argument.
    # When: Just validates the invocation.
    result = notebook_host.run(*args)
    # Then: rejection occurs before uv is started.
    assert result.returncode != 0
    assert diagnostic in result.stderr
    assert not (notebook_host.root / "argv").exists()


def test_notebook_child_failure_is_preserved(notebook_host: NotebookHost) -> None:
    # Given: a child that exits with status 37.
    notebook_host.env["FAKE_STATUS"] = "37"
    # When: Just waits for the notebook command.
    result = notebook_host.run("examples/05-failures-and-ci.py")
    # Then: the child's failure is not swallowed or replaced.
    assert result.returncode == 37, result.stderr
