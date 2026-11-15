from __future__ import annotations

import pytest

from perfcheck.collection_auth import (
    AuthConfig,
    AuthResolutionError,
    AuthScheme,
    resolve_auth,
)

_AUTH_SCHEME_ENV = "PERFCHECK_PROMETHEUS_AUTH_SCHEME"
_BEARER_TOKEN_ENV = "PERFCHECK_PROMETHEUS_BEARER_TOKEN"  # noqa: S105
_BASIC_USERNAME_ENV = "PERFCHECK_PROMETHEUS_BASIC_USERNAME"
_BASIC_PASSWORD_ENV = "PERFCHECK_PROMETHEUS_BASIC_PASSWORD"  # noqa: S105

_SECRET = "super-secret-value-93"  # noqa: S105 - synthetic auth test credential.


@pytest.mark.parametrize(
    ("inputs", "env", "expected"),
    [
        # scheme: an explicit flag wins over the environment scheme.
        (
            (AuthScheme.BEARER, "flag-token", None, None),
            {_AUTH_SCHEME_ENV: "none"},
            AuthConfig(AuthScheme.BEARER, "flag-token", None, None),
        ),
        # scheme: an explicit flag of none wins over an environment bearer.
        (
            (AuthScheme.NONE, "flag-token", None, None),
            {_AUTH_SCHEME_ENV: "bearer"},
            AuthConfig(AuthScheme.NONE, None, None, None),
        ),
        # bearer token: a flag wins over the environment token.
        (
            (None, "flag-token", None, None),
            {_BEARER_TOKEN_ENV: "env-token"},
            AuthConfig(AuthScheme.BEARER, "flag-token", None, None),
        ),
        # basic username: a flag wins over the environment username.
        (
            (AuthScheme.BASIC, None, "flag-user", "flag-pass"),
            {_BASIC_USERNAME_ENV: "env-user"},
            AuthConfig(AuthScheme.BASIC, None, "flag-user", "flag-pass"),
        ),
        # basic password: a flag wins over the environment password.
        (
            (AuthScheme.BASIC, None, "flag-user", "flag-pass"),
            {_BASIC_PASSWORD_ENV: "env-pass"},
            AuthConfig(AuthScheme.BASIC, None, "flag-user", "flag-pass"),
        ),
    ],
)
def test_flag_beats_env_for_each_surface(
    monkeypatch: pytest.MonkeyPatch,
    inputs: tuple[AuthScheme | str | None, str | None, str | None, str | None],
    env: dict[str, str],
    expected: AuthConfig,
) -> None:
    # Given: a CLI flag and an environment value that disagree for one surface.
    for name, value in env.items():
        monkeypatch.setenv(name, value)

    # When: resolve_auth receives the flag values with the environment set.
    config = resolve_auth(*inputs)

    # Then: the flag value wins for that surface and no secret leaks across.
    assert config == expected


def test_env_only_bearer_infers_scheme(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: only the bearer token environment variable is set.
    monkeypatch.setenv(_BEARER_TOKEN_ENV, "env-token")

    # When: resolve_auth is called with no flag and no scheme environment.
    config = resolve_auth(None, None, None, None)

    # Then: the scheme is inferred as bearer carrying that token.
    assert config == AuthConfig(AuthScheme.BEARER, "env-token", None, None)


def test_infer_basic_when_only_user_and_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: only the basic username and password environment variables are set.
    monkeypatch.setenv(_BASIC_USERNAME_ENV, "env-user")
    monkeypatch.setenv(_BASIC_PASSWORD_ENV, "env-pass")

    # When: resolve_auth is called with no flag and no scheme environment.
    config = resolve_auth(None, None, None, None)

    # Then: the scheme is inferred as basic carrying both credentials.
    assert config == AuthConfig(AuthScheme.BASIC, None, "env-user", "env-pass")


def test_infer_none_when_no_credentials() -> None:
    # Given: no flags and no relevant environment variables.

    # When: resolve_auth is called with all-None inputs.
    config = resolve_auth(None, None, None, None)

    # Then: the scheme resolves to none with no secrets.
    assert config == AuthConfig.NONE


def test_env_scheme_honored_when_no_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: an explicit scheme environment variable plus its credentials, and
    # no scheme flag.
    monkeypatch.setenv(_AUTH_SCHEME_ENV, "basic")
    monkeypatch.setenv(_BASIC_USERNAME_ENV, "env-user")
    monkeypatch.setenv(_BASIC_PASSWORD_ENV, "env-pass")

    # When: resolve_auth is called with no scheme flag.
    config = resolve_auth(None, None, None, None)

    # Then: the environment scheme wins over inference and carries its fields.
    assert config == AuthConfig(AuthScheme.BASIC, None, "env-user", "env-pass")


@pytest.mark.parametrize("scheme_arg", [AuthScheme.BEARER, "bearer"])
def test_resolve_rejects_bearer_without_token(
    scheme_arg: AuthScheme | str,
) -> None:
    # Given: an explicit bearer scheme but no token from flag or environment.

    # When: resolve_auth is called without a bearer token.
    with pytest.raises(AuthResolutionError) as caught:
        _ = resolve_auth(scheme_arg, None, None, None)

    # Then: the failure names the missing token field, never a secret value.
    assert str(caught.value) == "bearer auth requires a bearer token"
    assert _SECRET not in str(caught.value)


def test_resolve_rejects_basic_without_user() -> None:
    # Given: an explicit basic scheme with a password but no username.

    # When: resolve_auth is called without a basic username.
    with pytest.raises(AuthResolutionError) as caught:
        _ = resolve_auth(AuthScheme.BASIC, None, None, _SECRET)

    # Then: the failure names the missing username field, not the password secret.
    message = str(caught.value)
    assert "username" in message
    assert _SECRET not in message


def test_resolve_rejects_basic_without_password() -> None:
    # Given: an explicit basic scheme with a username but no password.

    # When: resolve_auth is called without a basic password.
    with pytest.raises(AuthResolutionError) as caught:
        _ = resolve_auth(AuthScheme.BASIC, None, "flag-user", None)

    # Then: the failure names the missing password field, not the username secret.
    message = str(caught.value)
    assert "password" in message
    assert "flag-user" not in message


def test_resolve_rejects_basic_flag_with_missing_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a basic scheme flag and a basic username from the environment, but
    # no basic password from either tier.
    monkeypatch.setenv(_BASIC_USERNAME_ENV, "env-user")

    # When: resolve_auth is called with a basic flag but no password.
    with pytest.raises(AuthResolutionError) as caught:
        _ = resolve_auth(AuthScheme.BASIC, None, None, None)

    # Then: the failure names the missing password field.
    message = str(caught.value)
    assert "password" in message
    assert "env-user" not in message


def test_none_carries_no_secrets() -> None:
    # Given: the shared default configuration constant.

    # When: AuthConfig.NONE is inspected.
    none = AuthConfig.NONE

    # Then: every secret field is absent.
    assert none.scheme is AuthScheme.NONE
    assert none.bearer_token is None
    assert none.basic_username is None
    assert none.basic_password is None


def test_non_applicable_secret_fields_are_none() -> None:
    # Given: a resolved bearer configuration and a resolved basic configuration.

    # When: each scheme is resolved with only its own credential present.
    bearer = resolve_auth(AuthScheme.BEARER, "tok", None, None)
    basic = resolve_auth(AuthScheme.BASIC, None, "user", "pass")

    # Then: the credential of one scheme never appears in the other's fields.
    assert bearer.basic_username is None
    assert bearer.basic_password is None
    assert basic.bearer_token is None


def test_error_message_contains_no_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a distinctive secret present in both the basic password and the
    # bearer token environment variables.
    monkeypatch.setenv(_BASIC_PASSWORD_ENV, _SECRET)
    monkeypatch.setenv(_BEARER_TOKEN_ENV, _SECRET)

    # When: resolution fails because the basic scheme is missing its username.
    with pytest.raises(AuthResolutionError) as caught:
        _ = resolve_auth(AuthScheme.BASIC, None, None, None)

    # Then: the message names the missing field only and never carries the secret.
    message = str(caught.value)
    assert "username" in message
    assert _SECRET not in message
