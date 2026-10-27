#!/bin/sh
set -eu

fail() { printf '%s\n' "$*" >&2; exit 2; }
root=${PERFCHECK_CONTAINER_HOST_ROOT:?Run through podman.just}
image=${PERFCHECK_CONTAINER_IMAGE:-localhost/perfcheck-dev:py314-uv0129-just1580}
case "$image" in -*) fail 'Image must be a reference, not a Podman option' ;; esac
action=$1
shift
case "$action" in
    build) exec podman build --http-proxy=false --tag "$image" --file "$root/Containerfile" "$root" ;;
    run|preview) ;;
    *) fail "Unknown adapter action: $action" ;;
esac

port=
if [ "$action" = preview ]; then
    port=${1-8000}
    case "$port" in ''|*[!0-9]*) fail 'Preview port must be 1..65535' ;; esac
    [ "${#port}" -le 5 ] && [ "$port" -ge 1 ] && [ "$port" -le 65535 ] ||
        fail 'Preview port must be 1..65535'
    set -- docs-preview 8000
elif [ "$#" -eq 0 ]; then
    set -- --list
fi

platform=$(uname -s)
source=${PERFCHECK_CONTAINER_SOURCE:-}
if [ -z "$source" ]; then
    [ "$platform" = Linux ] ||
        fail 'Set PERFCHECK_CONTAINER_SOURCE to an engine-visible absolute Linux path; VM sharing and ownership must be configured externally'
    source=$root
fi
case "$source" in /*) ;; *) fail 'Source must be an absolute Linux path' ;; esac
case "$source" in *:*|*\\*) fail 'Source must be a Linux path without mount delimiters' ;; esac
state=${PERFCHECK_CONTAINER_STATE_VOLUME:-}
if [ -z "$state" ]; then
    if command -v sha256sum >/dev/null 2>&1; then
        digest=$(printf '%s' "$root" | sha256sum)
    else
        digest=$(printf '%s' "$root" | shasum -a 256)
    fi
    digest=$(printf '%.12s' "$digest")
    state=perfcheck-dev-$digest-py314-v1
fi
if [ "${PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX+x}" = x ]; then
    [ "$PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX" = 1 ] ||
        fail 'PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX must be 1 when requested'
fi
case "$state" in ''|*[!a-zA-Z0-9_.-]*|[!a-zA-Z0-9]*) fail 'State must be a named volume' ;; esac

if [ -n "$port" ]; then
    set -- --publish "127.0.0.1:$port:8000" "$image" "$@"
else
    set -- "$image" "$@"
fi
if [ "${PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX+x}" = x ]; then
    set -- --env PERFCHECK_CONTAINER_BROWSER_NO_SANDBOX=1 "$@"
fi
if [ "$platform" = Linux ]; then
    set -- --userns=keep-id --volume "$source:/workspace:z" "$@"
else
    printf '%s\n' 'Remote/VM source sharing and writable ownership are caller-managed; native Linux keep-id/SELinux guarantees do not apply' >&2
    set -- --volume "$source:/workspace" "$@"
fi
exec podman run --rm --init --pull=never --http-proxy=false --workdir /workspace \
    --volume "$state:/container-state:U" "$@"
