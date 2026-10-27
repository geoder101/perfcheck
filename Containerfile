# Official multi-platform index digests verified from the registries on 2026-10-26.
FROM docker.io/library/python:3.14.7-slim-bookworm@sha256:82bc3c539b8813ada9d68c63b40158fa002f7f33de9bf3312a3dfdc0620dff56

COPY --from=ghcr.io/astral-sh/uv:0.12.9@sha256:8b940d3a9d65bed080436972241af2e21c84b5e8c9193f7014ed71479ee795ff /uv /uvx /usr/local/bin/

# Tool versions above/below are fixed; Debian packages use current Bookworm indexes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git gzip tar \
        chromium chromium-sandbox fonts-liberation fonts-dejavu-core \
        texlive-latex-base texlive-latex-recommended texlive-latex-extra dvisvgm \
    && rm -rf /var/lib/apt/lists/*

# Hashes match official 1.58.0/SHA256SUMS and locally downloaded release archives.
# https://github.com/casey/just/releases/download/1.58.0/SHA256SUMS
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
        amd64) target="x86_64-unknown-linux-musl"; sha256="4a5cc2f53e6f0f8c59092a6cc38291eb729d46a7dd95d3ae582008881b84931d" ;; \
        arm64) target="aarch64-unknown-linux-musl"; sha256="748237128c4c40cbdabc65e841d05ceba13cc23a91eaba395495894c1d9764df" ;; \
        *) printf '%s\n' 'Unsupported architecture: expected amd64 or arm64' >&2; exit 1 ;; \
    esac; \
    curl --fail --show-error --silent --location --retry 3 \
        "https://github.com/casey/just/releases/download/1.58.0/just-1.58.0-${target}.tar.gz" \
        --output /tmp/just.tar.gz \
    && printf '%s  %s\n' "$sha256" /tmp/just.tar.gz | sha256sum --check --strict \
    && tar -xzf /tmp/just.tar.gz -C /usr/local/bin just \
    && chmod 0755 /usr/local/bin/just \
    && rm /tmp/just.tar.gz

RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
        amd64) target="x64"; sha256="783130984963db7ba9cbd01089eaf2c2efb055c7c1693c943174b967b3050cb8" ;; \
        arm64) target="arm64"; sha256="6b4484c2190274175df9aa8f28e2d758a819cb1c1fe6ab481e2f95b463ab8508" ;; \
        *) printf '%s\n' 'Unsupported architecture: expected amd64 or arm64' >&2; exit 1 ;; \
    esac; \
    curl --fail --show-error --silent --location --retry 3 \
        "https://nodejs.org/dist/v24.18.0/node-v24.18.0-linux-${target}.tar.gz" \
        --output /tmp/node.tar.gz \
    && printf '%s  %s\n' "$sha256" /tmp/node.tar.gz | sha256sum --check --strict \
    && tar -xzf /tmp/node.tar.gz -C /usr/local --strip-components=1 \
    && rm /tmp/node.tar.gz

COPY tools/docs/package.json tools/docs/package-lock.json tools/docs/puppeteer*.json /opt/perfcheck-docs/
RUN PUPPETEER_SKIP_DOWNLOAD=true npm ci --ignore-scripts --prefix /opt/perfcheck-docs \
    && npm cache clean --force \
    && cat /etc/os-release && chromium --version \
    && useradd --create-home --uid 1000 perfcheck \
    && mkdir -p /container-state \
    && chown perfcheck:perfcheck /container-state

ENV UV_PROJECT_ENVIRONMENT=/container-state/venv \
    UV_CACHE_DIR=/container-state/uv-cache \
    HOME=/container-state \
    UV_PYTHON=/usr/local/bin/python3.14 \
    UV_PYTHON_DOWNLOADS=never \
    UV_LOCKED=true \
    PERFCHECK_DOCS_CONTAINER=1 \
    PERFCHECK_MERMAID_CLI=/opt/perfcheck-docs/node_modules/@mermaid-js/mermaid-cli/src/cli.js \
    PUPPETEER_SKIP_DOWNLOAD=true \
    XDG_CONFIG_HOME=/container-state/config \
    XDG_CACHE_HOME=/container-state/cache \
    PATH="/container-state/venv/bin:${PATH}"

WORKDIR /workspace
USER perfcheck
ENTRYPOINT ["just", "--justfile", "/workspace/justfile"]
CMD ["--list"]
