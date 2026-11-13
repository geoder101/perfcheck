# Official multi-platform index digests verified from the registries on 2026-10-26.
FROM docker.io/library/python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b

COPY --from=ghcr.io/astral-sh/uv:0.12.24@sha256:3af4716e991d6956a41e573eab705d0ee08500cd829ed30293eb8472f372c65a /uv /uvx /usr/local/bin/

# Tool versions above/below are fixed; Debian packages use current Bookworm indexes.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git gzip tar \
        chromium chromium-sandbox fonts-liberation fonts-dejavu-core \
        texlive-latex-base texlive-latex-recommended texlive-latex-extra dvisvgm \
    && rm -rf /var/lib/apt/lists/*

# Hashes match official 1.59.0/SHA256SUMS and locally downloaded release archives.
# https://github.com/casey/just/releases/download/1.59.0/SHA256SUMS
RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
        amd64) target="x86_64-unknown-linux-musl"; sha256="409044617b6f06517c1035e55ca38c8c856ff8b650e41bc2aa1ef82d5903a23e" ;; \
        arm64) target="aarch64-unknown-linux-musl"; sha256="23871b1702bfd550fb5f901778fd4290ecf2ee034a45a889fbe96d89b188086d" ;; \
        *) printf '%s\n' 'Unsupported architecture: expected amd64 or arm64' >&2; exit 1 ;; \
    esac; \
    curl --fail --show-error --silent --location --retry 3 \
        "https://github.com/casey/just/releases/download/1.59.0/just-1.59.0-${target}.tar.gz" \
        --output /tmp/just.tar.gz \
    && printf '%s  %s\n' "$sha256" /tmp/just.tar.gz | sha256sum --check --strict \
    && tar -xzf /tmp/just.tar.gz -C /usr/local/bin just \
    && chmod 0755 /usr/local/bin/just \
    && rm /tmp/just.tar.gz

RUN set -eu; \
    case "$(dpkg --print-architecture)" in \
        amd64) target="x64"; sha256="9f5eb6ac21845a66c493c91a253b1da32fd684e89e9b7202d4936982336be4ca" ;; \
        arm64) target="arm64"; sha256="df224555a083b918e46260cc969838501b9f9a87140c1195e5b9597b56d5dae2" ;; \
        *) printf '%s\n' 'Unsupported architecture: expected amd64 or arm64' >&2; exit 1 ;; \
    esac; \
    curl --fail --show-error --silent --location --retry 3 \
        "https://nodejs.org/dist/v24.18.1/node-v24.18.1-linux-${target}.tar.gz" \
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
