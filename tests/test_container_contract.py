import json
import shlex
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[1]


@pytest.fixture
def instructions() -> tuple[tuple[str, str], ...]:
    """Read logical instructions, leaving shell bodies intact for contract checks."""
    source = (ROOT / "Containerfile").read_text().replace("\\\n", " ")
    return tuple(
        (keyword.upper(), value.strip())
        for line in source.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
        for keyword, _, value in (line.strip().partition(" "),)
    )


def test_toolchain_uses_verified_versioned_images(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: a toolchain built independently of the working checkout.
    # When: its base and external binary sources are selected.
    bases = [value for key, value in instructions if key == "FROM"]
    copies = [
        shlex.split(value)
        for key, value in instructions
        if key == "COPY" and "--from=" in value
    ]
    # Then: both official multi-platform image inputs are immutable and versioned.
    python_digest = "82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56"
    uv_digest = "8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff"
    assert bases == [
        f"docker.io/library/python:3.14.7-slim-bookworm@sha256:{python_digest}"
    ]
    assert copies == [
        [
            f"--from=ghcr.io/astral-sh/uv:0.12.9@sha256:{uv_digest}",
            "/uv",
            "/uvx",
            "/usr/local/bin/",
        ]
    ]


@pytest.mark.parametrize(
    ("keyword", "expected"),
    [
        ("WORKDIR", "/workspace"),
        ("ENTRYPOINT", json.dumps(["just", "--justfile", "/workspace/justfile"])),
        ("CMD", json.dumps(["--list"])),
    ],
)
def test_image_runs_canonical_justfile(
    instructions: tuple[tuple[str, str], ...], keyword: str, expected: str
) -> None:
    # Given: the checkout will be mounted at runtime, not copied into the image.
    # When: the runtime command contract is inspected.
    values = [value for key, value in instructions if key == keyword]
    # Then: no alternate recipes or shell wrapper intercept the canonical command.
    assert values == [expected]


def test_environment_keeps_locked_state_outside_checkout(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: host .venv and container Python must never share environment files.
    # When: the persistent container environment is configured.
    environment = {
        name: setting
        for key, value in instructions
        if key == "ENV"
        for assignment in shlex.split(value)
        for name, _, setting in (assignment.partition("="),)
    }
    # Then: sync/run/build retain normal locking, syncing and build isolation.
    assert environment == {
        "UV_PROJECT_ENVIRONMENT": "/container-state/venv",
        "UV_CACHE_DIR": "/container-state/uv-cache",
        "HOME": "/container-state",
        "UV_PYTHON": "/usr/local/bin/python3.14",
        "UV_PYTHON_DOWNLOADS": "never",
        "UV_LOCKED": "true",
        "PATH": "/container-state/venv/bin:${PATH}",
        "PERFCHECK_DOCS_CONTAINER": "1",
        "PERFCHECK_MERMAID_CLI": (
            "/opt/perfcheck-docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js"
        ),
        "PUPPETEER_SKIP_DOWNLOAD": "true",
        "XDG_CONFIG_HOME": "/container-state/config",
        "XDG_CACHE_HOME": "/container-state/cache",
    }


def test_image_contains_documentation_and_development_os_tools(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: canonical check includes offline SVG math and Git-aware tooling.
    # When: the Debian package installation is inspected.
    installs = [
        value for key, value in instructions if key == "RUN" and "apt-get" in value
    ]
    assert len(installs) == 1
    tokens = shlex.split(installs[0])
    # Then: required tools are present without recommended extras or apt caches.
    assert {
        "git",
        "ca-certificates",
        "curl",
        "tar",
        "gzip",
        "texlive-latex-base",
        "texlive-latex-recommended",
        "texlive-latex-extra",
        "dvisvgm",
        "chromium",
        "chromium-sandbox",
        "fonts-liberation",
        "fonts-dejavu-core",
    } == set(tokens[7:-4])
    assert tokens[:7] == [
        "apt-get",
        "update",
        "&&",
        "apt-get",
        "install",
        "-y",
        "--no-install-recommends",
    ]
    assert tokens[-4:] == ["&&", "rm", "-rf", "/var/lib/apt/lists/*"]


def test_just_archives_are_verified_before_extraction(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: release SHA256SUMS and both downloaded archive hashes agree.
    amd64_sha = "4a5cc2f53e6f0f8c59092a6cc38291eb729d46a7dd95d3ae582008881b84931d"
    arm64_sha = "748237128c4c40cbdabc65e841d05ceba13cc23a91eaba395495894c1d9764df"
    expected = f"""set -eu;
case "$(dpkg --print-architecture)" in
    amd64) target="x86_64-unknown-linux-musl"; sha256="{amd64_sha}" ;;
    arm64) target="aarch64-unknown-linux-musl"; sha256="{arm64_sha}" ;;
    *) printf '%s\\n' 'Unsupported architecture: expected amd64 or arm64' >&2;
        exit 1 ;;
esac;
curl --fail --show-error --silent --location --retry 3
    "https://github.com/casey/just/releases/download/1.58.0/just-1.58.0-${{target}}.tar.gz"
    --output /tmp/just.tar.gz
&& printf '%s  %s\\n' "$sha256" /tmp/just.tar.gz | sha256sum --check --strict
&& tar -xzf /tmp/just.tar.gz -C /usr/local/bin just
&& chmod 0755 /usr/local/bin/just
&& rm /tmp/just.tar.gz
"""
    # When: the architecture-specific installer is inspected.
    installers = [
        value for key, value in instructions if key == "RUN" and "just.tar.gz" in value
    ]
    # Then: only the pinned official archive is extracted, after checksum success.
    assert [shlex.split(installer) for installer in installers] == [
        shlex.split(expected)
    ]


def test_image_build_does_not_install_project_or_define_services(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: all project dependency installation belongs to runtime just sync.
    # When: build actions and runtime declarations are inspected.
    keywords = {key for key, _ in instructions}
    runs = [value for key, value in instructions if key == "RUN"]
    # Then: no checkout ADD, dependency sync, service or implicit volume is baked in.
    assert not keywords & {"ADD", "EXPOSE", "HEALTHCHECK", "VOLUME"}
    assert not any("uv sync" in run for run in runs)


def test_build_context_is_a_strict_input_allowlist() -> None:
    # Given: the image requires no working source, secrets or generated evidence.
    # When: the build context policy is read without comments or blank lines.
    rules = [
        line.strip()
        for line in (ROOT / ".containerignore").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    # Then: arbitrary files (including future credentials) remain excluded by default.
    assert rules == [
        "**",
        "!Containerfile",
        "!.containerignore",
        "!tools/",
        "tools/**",
        "!tools/docs/",
        "tools/docs/**",
        "!tools/docs/package.json",
        "!tools/docs/package-lock.json",
        "!tools/docs/puppeteer.json",
        "!tools/docs/puppeteer-container.json",
        "!tools/docs/puppeteer-container-nosandbox.json",
    ]


def test_image_installs_locked_js_outside_checkout(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: JS dependencies must survive the runtime workspace mount.
    runs = [value for key, value in instructions if key == "RUN"]
    # When/Then: only locked manifests are installed without lifecycle scripts.
    assert any(
        "npm ci --ignore-scripts --prefix /opt/perfcheck-docs" in run for run in runs
    )
    assert ("USER", "perfcheck") in instructions
    assert any("/container-state" in run and "chown" in run for run in runs)
    assert any("chromium --version" in run and "/etc/os-release" in run for run in runs)


def test_node_archives_are_verified_before_extraction(
    instructions: tuple[tuple[str, str], ...],
) -> None:
    # Given: independently verified official Node 24.18.0 archive hashes.
    (installer,) = [
        value for key, value in instructions if key == "RUN" and "node.tar.gz" in value
    ]
    # When/Then: both supported architectures check the archive before unpacking.
    assert (
        "783130984963db7ba9cbd01089eaf2c2efb055c7c1693c943174b967b3050cb8" in installer
    )
    assert (
        "6b4484c2190274175df9aa8f28e2d758a819cb1c1fe6ab481e2f95b463ab8508" in installer
    )
    assert (
        "https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-${target}.tar.gz"
        in installer
    )
    assert installer.index("sha256sum --check --strict") < installer.index("tar -xzf")
