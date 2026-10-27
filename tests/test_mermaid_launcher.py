from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Final

import pytest
from tools import mermaid

ROOT: Final = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "PERFCHECK_MERMAID_CLI",
        "PERFCHECK_DOCS_CONTAINER",
        "PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX",
    ):
        monkeypatch.delenv(key, raising=False)


def test_selected_js_preserves_arguments_streams_and_failure(tmp_path: Path) -> None:
    # Given: an explicit JS entry point with a failing child and literal arguments.
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable")
    script = tmp_path / "selected cli.mjs"
    _ = script.write_text(
        """console.log(JSON.stringify(process.argv.slice(2)));
console.error('selected stderr');process.exit(37);"""
    )
    args = ["two words", "", "雪", "$(touch sentinel)", "&|<>;", 'a"b', "end\\"]
    # When: the real launcher executes its selected child.
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "tools/mermaid.py"), *args],
        env={**os.environ, "PERFCHECK_MERMAID_CLI": str(script)},
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    # Then: no shell, retry, installer, or alternative renderer intercepts failure.
    assert result.returncode == 37, result.stderr
    assert json.loads(result.stdout) == [
        *args,
        "--puppeteerConfigFile",
        str(ROOT / "tools/docs/puppeteer.json"),
    ]
    assert result.stderr == "selected stderr\n"


@pytest.mark.parametrize("override", ["relative.js", "", "/missing/cli.js"])
def test_invalid_explicit_cli_fails_without_fallback(
    override: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: explicit invalid configuration despite available global tools.
    monkeypatch.setenv("PERFCHECK_MERMAID_CLI", override)
    # When/Then: resolution rejects configuration instead of falling back.
    with pytest.raises(mermaid.LauncherError):
        _ = mermaid.command([], ROOT)


@pytest.mark.parametrize(
    ("container", "opt_in", "profile"),
    [
        (None, None, "puppeteer.json"),
        ("1", None, "puppeteer-container.json"),
        ("1", "1", "puppeteer-container-nosandbox.json"),
    ],
)
def test_profile_selection_is_explicit(
    container: str | None,
    opt_in: str | None,
    profile: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a valid explicit JS entry and a container-only opt-in.
    monkeypatch.setenv("PERFCHECK_MERMAID_CLI", str(Path(__file__).resolve()))
    if container is not None:
        monkeypatch.setenv("PERFCHECK_DOCS_CONTAINER", container)
    if opt_in is not None:
        monkeypatch.setenv("PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX", opt_in)
    # When: command configuration is resolved.
    argv = mermaid.command([], ROOT)
    # Then: native mode never silently selects the system browser or disables sandbox.
    assert argv[-1] == str(ROOT / "tools/docs" / profile)


@pytest.mark.parametrize(
    ("container", "opt_in"), [(None, "1"), ("1", "0"), ("1", "true"), ("1", "")]
)
def test_invalid_sandbox_override_is_rejected(
    container: str | None, opt_in: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a malformed or native-host sandbox override.
    if container is not None:
        monkeypatch.setenv("PERFCHECK_DOCS_CONTAINER", container)
    monkeypatch.setenv("PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX", opt_in)
    # When/Then: reject before execution, including explicit empty values.
    with pytest.raises(mermaid.LauncherError):
        _ = mermaid.command([], ROOT)


def test_windows_uses_local_js_and_real_node(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: Windows with a local JS entry point, not a .cmd shell shim.
    script = tmp_path / "tools/docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    script.parent.mkdir(parents=True)
    script.touch()
    monkeypatch.setattr(sys, "platform", "win32")

    def which(name: str) -> str:
        return "C:/node/node.exe" if name == "node" else "C:/bin/mmdc.cmd"

    monkeypatch.setattr(shutil, "which", which)
    # When: the launcher selects its executable vector.
    argv = mermaid.command(["-i", "a & b.mmd"], tmp_path)
    # Then: the actual node binary receives JS and arguments directly.
    assert argv[:4] == ["C:/node/node.exe", str(script), "-i", "a & b.mmd"]


def test_posix_global_fallback_only_when_local_js_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: no checkout tools but a user-owned global mmdc installation.
    monkeypatch.setattr(sys, "platform", "linux")

    def which(_name: str) -> str:
        return "/user/bin/mmdc"

    monkeypatch.setattr(shutil, "which", which)
    # When: resolution runs without an override.
    argv = mermaid.command(["--version"], tmp_path)
    # Then: the installed executable remains a supported POSIX fallback.
    assert argv[:2] == ["/user/bin/mmdc", "--version"]


@pytest.mark.parametrize("platform", ["win32", "linux"])
def test_selected_local_js_requires_node_without_global_retry(
    platform: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: a selected local JS CLI but no actual Node executable.
    script = tmp_path / "tools/docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
    script.parent.mkdir(parents=True)
    script.touch()
    lookups: list[str] = []

    def which(name: str) -> str | None:
        lookups.append(name)
        return None

    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(shutil, "which", which)
    # When/Then: resolution fails without searching for mmdc, npm, npx, or Bun.
    with pytest.raises(mermaid.LauncherError):
        _ = mermaid.command([], tmp_path)
    assert lookups == ["node"]


def test_windows_rejects_global_cmd_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given: no local JS CLI on Windows, even if shell shims exist on PATH.
    monkeypatch.setattr(sys, "platform", "win32")
    # When/Then: the launcher refuses to resolve mmdc.cmd through a shell.
    with pytest.raises(mermaid.LauncherError):
        _ = mermaid.command([], tmp_path)


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("puppeteer.json", {"headless": True}),
        (
            "puppeteer-container.json",
            {"headless": True, "executablePath": "/usr/bin/chromium"},
        ),
        (
            "puppeteer-container-nosandbox.json",
            {
                "headless": True,
                "executablePath": "/usr/bin/chromium",
                "args": ["--no-sandbox"],
            },
        ),
    ],
)
def test_browser_profiles_use_regular_headless(
    filename: str, expected: dict[str, bool | str | list[str]]
) -> None:
    # Given: checked-in explicit launch profiles.
    # When: their actual serialized options are loaded.
    # Then: only the explicit opt-in profile disables sandboxing; none use shell.
    assert json.loads((ROOT / "tools/docs" / filename).read_text()) == expected


def test_js_manifest_and_npm_lock_agree_on_exact_versions() -> None:
    # Given: independently provisioned JavaScript tools with a real npm lockfile.
    manifest = ROOT / "tools/docs/package.json"
    lock = ROOT / "tools/docs/package-lock.json"
    # When/Then: both the requested and resolved dependency versions stay exact.
    assert json.loads(manifest.read_text())["dependencies"] == {
        "@mermaid-js/mermaid-cli": "12.0.0",
        "puppeteer": "25.16.0",
    }
    assert json.loads(manifest.read_text())["engines"] == {"node": "24.18.0"}
    assert json.loads(lock.read_text())["lockfileVersion"] == 3
    assert (
        json.loads(lock.read_text())["packages"][
            "node_modules/@mermaid-js/mermaid-cli"
        ]["version"]
        == "12.0.0"
    )
    assert (
        json.loads(lock.read_text())["packages"]["node_modules/puppeteer"]["version"]
        == "25.16.0"
    )


def test_workflow_browser_installer_is_real_locked_cli() -> None:
    # Given: explicitly installed local packages, not an npx download fallback.
    if not (ROOT / "tools/docs/node_modules/puppeteer/package.json").is_file():
        pytest.skip("Optional local JS tools are not provisioned")
    node = shutil.which("node")
    assert node
    for workflow in ("ci.yml", "pages.yml"):
        text = (ROOT / ".github/workflows" / workflow).read_text()
        entries = {
            match[1]
            for match in re.finditer(
                r"node (tools/docs/\S+) browsers install chrome", text
            )
        }
        assert entries
        for entry in entries:
            relative = Path(entry).relative_to("tools/docs/node_modules/puppeteer")
            metadata = ROOT / "tools/docs/node_modules/puppeteer/package.json"
            assert json.loads(metadata.read_text())["bin"] == f"./{relative.as_posix()}"
            # When: CI's exact local installer entry is run without installation.
            result = subprocess.run(  # noqa: S603
                [node, str(ROOT / entry), "--help"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            # Then: the pinned distribution actually provides that CLI path.
            assert result.returncode == 0, result.stderr


def test_apparmor_attachment_matches_pinned_puppeteer_chrome() -> None:
    # Given: the installed locked Puppeteer package, without a browser download.
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable; cannot query installed Puppeteer revision")
    if not (ROOT / "tools/docs/node_modules/puppeteer/package.json").is_file():
        pytest.skip("Optional locked Puppeteer tooling is not provisioned")
    script = """const p = require('./tools/docs/node_modules/puppeteer');
const meta = require('./tools/docs/node_modules/puppeteer/package.json');
console.log(meta.version);
console.log(p.PUPPETEER_REVISIONS.chrome);"""
    # When: Node reads the package's bundled Chrome revision, without launching it.
    result = subprocess.run(  # noqa: S603
        [node, "-e", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    # Then: the installed package matches its pin and the exact AppArmor attachment.
    assert result.returncode == 0, result.stderr
    version, revision = result.stdout.splitlines()
    assert (
        version
        == json.loads((ROOT / "tools/docs/package.json").read_text())["dependencies"][
            "puppeteer"
        ]
    )
    profile = (ROOT / "tools/docs/chrome-apparmor").read_text(encoding="utf-8")
    attachment = re.search(r"profile perfcheck-chrome (\S+) flags=", profile)
    assert attachment
    expected = (
        f"/home/runner/.cache/puppeteer/chrome/linux-{revision}/chrome-linux64/chrome"
    )
    assert attachment[1] == expected
