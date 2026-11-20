from __future__ import annotations

import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import anyio

if TYPE_CHECKING:
    import pytest


_ROOT = Path(__file__).parents[2]


def _isolated_environment() -> dict[str, str]:
    environment = dict(os.environ)
    for variable in (
        "PYTHONHOME",
        "PYTHONPATH",
        "UV_PROJECT",
        "UV_WORKING_DIRECTORY",
        "VIRTUAL_ENV",
    ):
        _ = environment.pop(variable, None)
    return environment


def _run(command: tuple[str, ...], environment: dict[str, str], cwd: Path) -> int:
    return anyio.run(_run_process, command, environment, cwd)


async def _run_process(
    command: tuple[str, ...], environment: dict[str, str], cwd: Path
) -> int:
    with anyio.fail_after(30):
        result = await anyio.run_process(command, check=False, cwd=cwd, env=environment)
    return result.returncode


def _uv_executable() -> str:
    executable = shutil.which("uv")
    assert executable is not None
    return executable


def _venv_python(venv: Path) -> Path:
    executable = "python.exe" if os.name == "nt" else "python"
    directory = "Scripts" if os.name == "nt" else "bin"
    return venv / directory / executable


def _venv_cli(venv: Path) -> Path:
    executable = "perfcheck.exe" if os.name == "nt" else "perfcheck"
    directory = "Scripts" if os.name == "nt" else "bin"
    return venv / directory / executable


def _build_wheel(artifacts: Path) -> Path:
    uv = _uv_executable()
    return_code = _run(
        (
            uv,
            "--directory",
            str(_ROOT),
            "build",
            "--wheel",
            "--out-dir",
            str(artifacts),
        ),
        _isolated_environment(),
        artifacts.parent,
    )
    assert return_code == 0
    (wheel,) = artifacts.glob("perfcheck-*.whl")
    return wheel


def _install_wheel(venv: Path, wheel: Path) -> tuple[Path, Path]:
    environment = _isolated_environment()
    interpreter = _venv_python(venv)
    assert (
        _run((sys.executable, "-m", "venv", str(venv)), environment, venv.parent) == 0
    )
    assert (
        _run(
            (
                _uv_executable(),
                "pip",
                "install",
                "--python",
                str(interpreter),
                str(wheel),
            ),
            environment,
            venv.parent,
        )
        == 0
    )
    return interpreter, _venv_cli(venv)


def _without_package(wheel: Path, target: Path) -> Path:
    with zipfile.ZipFile(wheel) as source, zipfile.ZipFile(target, "w") as artifact:
        for entry in source.infolist():
            if not entry.filename.startswith("perfcheck/"):
                artifact.writestr(entry, source.read(entry))
    return target


def test_check_requires_lock_and_build_gates() -> None:
    # Given: the portable local verification recipe and CI workflow.
    recipe = (_ROOT / "justfile").read_text(encoding="utf-8")
    workflow = (_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    # When: deterministic gates and their cross-platform runners are inspected.

    # Then: Just uses platform-native shells, owns all gates, and CI invokes it.
    check_dependencies = (
        "lock-check",
        "schema-check",
        "format-check",
        "lint",
        "typecheck",
        "test",
        "examples-check",
        "docs-check",
        "build",
    )
    assert '[unix]\nset shell := ["sh", "-cu"]' in recipe
    assert '[windows]\nset shell := ["powershell.exe", "-NoLogo", "-Command"]' in recipe
    assert f"check: {' '.join(check_dependencies)}" in recipe
    assert "uses: ./.github/actions/toolchain" in workflow
    assert "- run: just check" in workflow


def test_fresh_wheel_installs_without_checkout_or_editable_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a wheel built from the checkout and an empty virtual environment.
    monkeypatch.chdir(tmp_path)
    wheel = _build_wheel(tmp_path / "artifacts")
    interpreter, command = _install_wheel(tmp_path / "venv", wheel)
    environment = _isolated_environment()

    # When: only the installed wheel is imported and its generated CLI is invoked.
    import_exit = _run(
        (str(interpreter), "-I", "-c", "import perfcheck"), environment, tmp_path
    )
    help_exit = _run((str(command), "--help"), environment, tmp_path)

    # Then: both public installed surfaces succeed outside the checkout environment.
    assert import_exit == 0
    assert help_exit == 0


def test_fresh_wheel_check_detects_a_missing_package(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a disposable wheel whose import package was removed after build.
    monkeypatch.chdir(tmp_path)
    wheel = _build_wheel(tmp_path / "artifacts")
    incomplete_wheel = _without_package(wheel, tmp_path / wheel.name)
    interpreter, _ = _install_wheel(tmp_path / "venv", incomplete_wheel)

    # When: the clean environment imports the installed distribution.
    import_exit = _run(
        (str(interpreter), "-I", "-c", "import perfcheck"),
        _isolated_environment(),
        tmp_path,
    )

    # Then: the E2E probe fails rather than accepting the malformed artifact.
    assert import_exit != 0
