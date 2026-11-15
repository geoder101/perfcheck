"""Resolved Prometheus HTTP authentication configuration for collection."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum, unique
from typing import ClassVar, Final, assert_never, override

from perfcheck.errors import PerfcheckError

__all__ = [
    "AuthConfig",
    "AuthResolutionCode",
    "AuthResolutionError",
    "AuthScheme",
    "resolve_auth",
]

_AUTH_SCHEME_ENV: Final = "PERFCHECK_PROMETHEUS_AUTH_SCHEME"
_BEARER_TOKEN_ENV: Final = "PERFCHECK_PROMETHEUS_BEARER_TOKEN"  # noqa: S105
_BASIC_USERNAME_ENV: Final = "PERFCHECK_PROMETHEUS_BASIC_USERNAME"
_BASIC_PASSWORD_ENV: Final = "PERFCHECK_PROMETHEUS_BASIC_PASSWORD"  # noqa: S105

_ENV_NAMES: Final = (
    _AUTH_SCHEME_ENV,
    _BEARER_TOKEN_ENV,
    _BASIC_USERNAME_ENV,
    _BASIC_PASSWORD_ENV,
)


@unique
class AuthScheme(StrEnum):
    """Supported Prometheus HTTP authentication schemes."""

    NONE = "none"
    BEARER = "bearer"
    BASIC = "basic"


@dataclass(frozen=True, slots=True)
class AuthConfig:
    """Resolved HTTP authentication for one Prometheus collection.

    Only the fields that apply to ``scheme`` are ever populated; the remaining
    secret fields stay ``None`` so a resolved configuration never carries a
    credential that does not belong to its scheme.
    """

    scheme: AuthScheme = AuthScheme.NONE
    bearer_token: str | None = None
    basic_username: str | None = None
    basic_password: str | None = None
    NONE: ClassVar[AuthConfig]


AuthConfig.NONE = AuthConfig(AuthScheme.NONE, None, None, None)


class AuthResolutionCode(StrEnum):
    """Stable typed, secret-free reasons a resolved configuration is invalid."""

    BEARER_REQUIRES_TOKEN = "bearer auth requires a bearer token"  # noqa: S105
    BASIC_REQUIRES_USERNAME = "basic auth requires a username"
    BASIC_REQUIRES_PASSWORD = "basic auth requires a password"  # noqa: S105
    BASIC_REQUIRES_USERNAME_AND_PASSWORD = (
        "basic auth requires a username and a password"  # noqa: S105
    )


@dataclass(frozen=True, slots=True)
class AuthResolutionError(PerfcheckError):
    """The resolved auth configuration is incomplete or inconsistent."""

    code: AuthResolutionCode

    @override
    def __str__(self) -> str:
        """Render the secret-free reason for command-line diagnostics."""
        return self.code


def resolve_auth(
    scheme: AuthScheme | str | None,
    bearer_token: str | None,
    basic_username: str | None,
    basic_password: str | None,
) -> AuthConfig:
    """Resolve Prometheus HTTP auth from CLI flags with env-var fallback.

    Each argument is a CLI-flag value (or ``None``). A provided flag wins over
    the matching environment variable; only those two tiers participate. When no
    scheme is chosen by either tier, the scheme is inferred from whichever
    credentials are present. The returned configuration carries no secret that
    does not belong to its resolved scheme.
    """
    env = _read_env()
    resolved_scheme = _resolve_scheme(scheme, env[_AUTH_SCHEME_ENV])
    resolved_bearer = _merge(bearer_token, env[_BEARER_TOKEN_ENV])
    resolved_username = _merge(basic_username, env[_BASIC_USERNAME_ENV])
    resolved_password = _merge(basic_password, env[_BASIC_PASSWORD_ENV])
    if resolved_scheme is None:
        resolved_scheme = _infer_scheme(
            resolved_bearer, resolved_username, resolved_password
        )
    return _build(
        resolved_scheme, resolved_bearer, resolved_username, resolved_password
    )


def _read_env() -> dict[str, str | None]:
    """Read the four Prometheus auth environment variables in one pass."""
    return {name: os.getenv(name) for name in _ENV_NAMES}


def _resolve_scheme(
    scheme: AuthScheme | str | None, env_scheme: str | None
) -> AuthScheme | None:
    """Return the explicit scheme from the flag tier, then the env tier."""
    cli_scheme = _coerce_scheme(scheme)
    if cli_scheme is not None:
        return cli_scheme
    if env_scheme:
        return _coerce_scheme(env_scheme)
    return None


def _coerce_scheme(value: AuthScheme | str | None) -> AuthScheme | None:
    if value is None:
        return None
    return AuthScheme(value)


def _merge(cli_value: str | None, env_value: str | None) -> str | None:
    """Return the CLI flag when present, else the environment value."""
    if cli_value:
        return cli_value
    if env_value:
        return env_value
    return None


def _infer_scheme(
    bearer_token: str | None,
    basic_username: str | None,
    basic_password: str | None,
) -> AuthScheme:
    """Infer a scheme from whichever credentials are present, else ``none``."""
    if bearer_token:
        return AuthScheme.BEARER
    if basic_username and basic_password:
        return AuthScheme.BASIC
    return AuthScheme.NONE


def _build(
    scheme: AuthScheme,
    bearer_token: str | None,
    basic_username: str | None,
    basic_password: str | None,
) -> AuthConfig:
    """Validate the resolved scheme and build a scheme-appropriate config."""
    match scheme:
        case AuthScheme.BEARER:
            if not bearer_token:
                raise AuthResolutionError(AuthResolutionCode.BEARER_REQUIRES_TOKEN)
            return AuthConfig(scheme, bearer_token, None, None)
        case AuthScheme.BASIC:
            if not basic_username and not basic_password:
                raise AuthResolutionError(
                    AuthResolutionCode.BASIC_REQUIRES_USERNAME_AND_PASSWORD
                )
            if not basic_username:
                raise AuthResolutionError(AuthResolutionCode.BASIC_REQUIRES_USERNAME)
            if not basic_password:
                raise AuthResolutionError(AuthResolutionCode.BASIC_REQUIRES_PASSWORD)
            return AuthConfig(scheme, None, basic_username, basic_password)
        case AuthScheme.NONE:
            return AuthConfig(scheme, None, None, None)
        case _:
            assert_never(scheme)
