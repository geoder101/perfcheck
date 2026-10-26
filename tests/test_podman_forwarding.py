import hashlib
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]
IMAGE: Final = "localhost/perfcheck-dev:py314-uv0129-just1580"


class ShellRequest(Protocol):
    @property
    def param(self) -> str: ...


@dataclass(frozen=True, slots=True)
class Host:
    root: Path
    cwd: Path
    env: dict[str, str]

    def run(self, *args: str) -> subprocess.CompletedProcess[str]:
        just = shutil.which("just")
        assert just
        return subprocess.run(  # noqa: S603
            [just, "--justfile", str(self.root / "podman.just"), *args],
            cwd=self.cwd,
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def argv(self) -> list[str]:
        return (self.cwd / "argv").read_bytes().decode().split("\0")[:-1]


@pytest.fixture(params=["sh", "pwsh"])
def host(tmp_path: Path, request: ShellRequest) -> Host:
    if sys.platform != "linux" or not shutil.which("just"):
        pytest.skip("fake executable harness requires Linux and host Just")
    powershell = request.param == "pwsh"
    if powershell and not shutil.which("pwsh"):
        pytest.skip("PowerShell 7 unavailable (Windows 5.1 is not tested here)")
    root = tmp_path / "checkout with spaces"
    root.mkdir()
    (root / "tools").mkdir()
    adapter = ROOT / "podman.just"
    justfile = adapter.read_text() if adapter.exists() else ""
    if powershell:
        # Exercise the Windows recipes with the available Unix PowerShell host.
        justfile = justfile.replace("[unix]", "[swap]")
        justfile = justfile.replace("[windows]", "[unix]")
        justfile = justfile.replace("[swap]", "[windows]")
        justfile = justfile.replace("powershell.exe", "pwsh")
    _ = (root / "podman.just").write_text(justfile)
    for name in ("podman.sh", "podman.ps1"):
        source = ROOT / "tools" / name
        if source.exists():
            _ = shutil.copyfile(source, root / "tools" / name)
    cwd = tmp_path / "elsewhere"
    cwd.mkdir()
    binary = tmp_path / "bin"
    binary.mkdir()
    fake = binary / "podman"
    _ = fake.write_text(
        r"""#!/bin/sh
printf '%s\0' "$@" > "$RECEIPT"
printf 'child stdout\n'
printf 'child stderr\n' >&2
exit "${FAKE_STATUS:-0}"
"""
    )
    fake.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PERFCHECK_")}
    env.update(PATH=f"{binary}:{env['PATH']}", RECEIPT=str(cwd / "argv"))
    return Host(root, cwd, env)


@pytest.mark.parametrize("args", [(), ("run",), ("run", "test"), ("run", "--list")])
def test_default_and_named_forwarding(host: Host, args: tuple[str, ...]) -> None:
    # Given: the optional Just interface and a recording engine.
    # When: a default, named, or option command is requested.
    result = host.run(*args)
    # Then: the image entrypoint gets exactly the requested command.
    assert result.returncode == 0, result.stderr
    argv = host.argv()
    assert argv[argv.index(IMAGE) + 1 :] == list(args[1:] or ("--list",))


def test_arguments_are_data_not_shell(host: Host) -> None:
    # Given: adversarial and platform-sensitive argument boundaries.
    args = (
        "cli",
        "two words",
        "",
        "雪",
        'a"b',
        "end\\",
        "end\\\n",
        "end\\\\",
        'two\\\\"quotes',
        'x\\"y',
        "$(touch sentinel)",
        "; touch sentinel",
        "&|<>$`'{}*?",
    )
    # When: host Just forwards the complete vector.
    result = host.run("run", *args)
    # Then: no shell interprets the data or loses an empty argument.
    assert result.returncode == 0, result.stderr
    argv = host.argv()
    assert argv[argv.index(IMAGE) + 1 :] == list(args)
    assert not (host.root / "sentinel").exists()
    assert not (host.cwd / "sentinel").exists()


def test_run_requests_checkout_and_state_mount_options(host: Host) -> None:
    # Given: a checkout with spaces, invoked from an unrelated directory.
    digest = hashlib.sha256(str(host.root).encode()).hexdigest()[:12]
    # When: the adapter calls the recording executable.
    result = host.run("run")
    # Then: argv requests keep-id and reserves :U for the named state volume.
    assert result.returncode == 0, result.stderr
    argv = host.argv()
    assert argv[:5] == ["run", "--rm", "--init", "--pull=never", "--http-proxy=false"]
    assert "--userns=keep-id" in argv
    assert f"{host.root}:/workspace:z" in argv
    assert f"perfcheck-dev-{digest}-py314-v1:/container-state:U" in argv
    assert argv[argv.index("--workdir") + 1] == "/workspace"
    assert not any(x in argv for x in ("-t", "--tty", "--network=host", "--publish"))


def test_overrides(host: Host) -> None:
    # Given: explicit engine-visible source, image, and state identities.
    host.env.update(
        PERFCHECK_CONTAINER_SOURCE="/engine/checkout space",
        PERFCHECK_CONTAINER_IMAGE="localhost/custom:tag",
        PERFCHECK_CONTAINER_STATE_VOLUME="custom-state",
    )
    # When: a command is forwarded.
    result = host.run("run", "sync")
    # Then: no checkout ownership option leaks onto the bind mount.
    assert result.returncode == 0, result.stderr
    argv = host.argv()
    assert "/engine/checkout space:/workspace:z" in argv
    assert "custom-state:/container-state:U" in argv
    assert argv[-2:] == ["localhost/custom:tag", "sync"]


def test_build_context(host: Host) -> None:
    # Given: a caller outside the checkout.
    # When: the image build is requested.
    result = host.run("build")
    # Then: Podman builds the checkout's Containerfile and context.
    assert result.returncode == 0, result.stderr
    assert host.argv() == [
        "build",
        "--http-proxy=false",
        "--tag",
        IMAGE,
        "--file",
        str(host.root / "Containerfile"),
        str(host.root),
    ]


@pytest.mark.parametrize("port", [None, "8765", "1", "65535"])
def test_preview_publish(host: Host, port: str | None) -> None:
    # Given: a valid host port, with the container server fixed at 8000.
    args = () if port is None else (port,)
    # When: preview is requested.
    result = host.run("preview", *args)
    # Then: only the loopback host port is published.
    assert result.returncode == 0, result.stderr
    argv = host.argv()
    assert argv[argv.index("--publish") + 1] == f"127.0.0.1:{port or '8000'}:8000"
    assert argv[-3:] == [IMAGE, "docs-preview", "8000"]


@pytest.mark.parametrize(
    "port", ["0", "65536", "-1", "abc", "", "1;touch sentinel", "1\n"]
)
def test_invalid_preview_rejected_before_engine(host: Host, port: str) -> None:
    # Given: an invalid port including shell syntax.
    # When: preview is requested.
    result = host.run("preview", port)
    # Then: validation fails before invoking Podman.
    assert result.returncode != 0
    assert "1..65535" in result.stderr
    assert not (host.cwd / "argv").exists()


def test_exit_and_streams(host: Host) -> None:
    # Given: a child with distinct streams and status 37.
    host.env["FAKE_STATUS"] = "37"
    # When: host Just waits for the child.
    result = host.run("run", "test")
    # Then: neither the failure nor either stream is swallowed.
    assert result.returncode == 37
    assert result.stdout == "child stdout\n"
    assert "child stderr\n" in result.stderr


def test_missing_podman(host: Host) -> None:
    # Given: no executable at the engine boundary.
    binary = Path(host.env["PATH"].split(":")[0])
    (binary / "podman").unlink()
    for name in ("sh", "uname", "sha256sum", "pwsh", "dotnet"):
        command = shutil.which(name)
        if command:
            (binary / name).symlink_to(command)
    host.env["PATH"] = str(binary)
    # When: a command is requested.
    result = host.run("run")
    # Then: start failure is a diagnostic nonzero result.
    assert result.returncode == 127, result.stderr
    assert "podman" in result.stderr.lower()


@pytest.mark.parametrize("source", ["relative", "C:\\checkout", "/bad:options"])
def test_source_requires_unambiguous_linux_path(host: Host, source: str) -> None:
    # Given: a source that cannot safely denote an engine-side bind path.
    host.env["PERFCHECK_CONTAINER_SOURCE"] = source
    # When: a run is requested.
    result = host.run("run")
    # Then: no guessed Windows conversion or mount option injection occurs.
    assert result.returncode != 0
    assert not (host.cwd / "argv").exists()


@pytest.mark.parametrize("volume", ["/host/path", "name:options", "-bad", "a b", "a\n"])
def test_state_override_requires_named_volume(host: Host, volume: str) -> None:
    # Given: a bind path or invalid volume name instead of isolated state.
    host.env["PERFCHECK_CONTAINER_STATE_VOLUME"] = volume
    # When: the transport is invoked.
    result = host.run("run")
    # Then: :U cannot recursively chown an arbitrary host bind path.
    assert result.returncode != 0
    assert "named volume" in result.stderr
    assert not (host.cwd / "argv").exists()


def test_build_honors_image_override(host: Host) -> None:
    # Given: an explicit local tag and an unrelated engine-side source.
    host.env.update(
        PERFCHECK_CONTAINER_IMAGE="localhost/other:tag",
        PERFCHECK_CONTAINER_SOURCE="/engine/source",
    )
    # When: building the image.
    result = host.run("build")
    # Then: the host checkout remains the build context, not the runtime bind.
    assert result.returncode == 0, result.stderr
    assert host.argv() == [
        "build",
        "--http-proxy=false",
        "--tag",
        "localhost/other:tag",
        "--file",
        str(host.root / "Containerfile"),
        str(host.root),
    ]


@pytest.mark.parametrize("action", ["build", "run", "preview"])
def test_image_override_cannot_inject_options(host: Host, action: str) -> None:
    # Given: an option-shaped value where an image reference is required.
    host.env["PERFCHECK_CONTAINER_IMAGE"] = "--privileged"
    # When: the transport is invoked.
    result = host.run(action)
    # Then: image configuration cannot change engine privileges.
    assert result.returncode != 0
    assert not (host.cwd / "argv").exists()


@pytest.mark.parametrize("recipe", ["run *args", "build", 'preview port="8000"'])
def test_windows_launch_uses_process_execution_policy(recipe: str) -> None:
    # Given: the actual host launch configuration, not the Linux test rewrite.
    source = (ROOT / "podman.just").read_text()
    # When: Windows script interpreters are read for each recipe.
    launches = {
        match[2]: match[1]
        for match in re.finditer(r"\[script\((.*?)\)\]\n\[windows\]\n([^\n]+):", source)
    }
    # Then: Bypass is process-scoped and precedes the final -File option.
    expected = [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
    ]
    assert launches[recipe] == ", ".join(f'"{arg}"' for arg in expected)


@pytest.mark.parametrize("action", ["build", "run", "preview"])
def test_proxy_forwarding_is_explicitly_disabled(host: Host, action: str) -> None:
    # Given: both cases of host proxy variables, with synthetic values only.
    names = ("http_proxy", "https_proxy", "ftp_proxy", "all_proxy", "no_proxy")
    proxies = {
        key: f"synthetic-{key}" for name in names for key in (name, name.upper())
    }
    host.env.update(proxies)
    # When: a build or run reaches the recording executable.
    result = host.run(action)
    # Then: default proxy propagation is disabled, without manual forwarding.
    assert result.returncode == 0, result.stderr
    argv = host.argv()
    assert argv.count("--http-proxy=false") == 1
    assert not any(arg.startswith(("--env", "--build-arg", "-e")) for arg in argv)
    assert not any(
        name in arg or value in arg for name, value in proxies.items() for arg in argv
    )
