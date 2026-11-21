from __future__ import annotations

import json

import httpx2
import pytest

from perfcheck.prometheus_response import redact_json, redact_text, response_provenance


def test_response_facade_preserves_redacted_valid_response_provenance() -> None:
    # Given: a valid upstream response containing a bearer credential in evidence.
    response = httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
            "warnings": ["Bearer top-secret"],
        },
    )

    # When: the established response facade parses the response.
    parsed = response_provenance(response, ("top-secret",))

    # Then: its public helpers retain the secret-safe compatibility contract.
    assert parsed.provenance.status_code == 200
    assert parsed.provenance.warnings == ("Bearer [REDACTED]",)
    assert redact_json({"authorization": "top-secret"}, ("top-secret",)) == {
        "[REDACTED]": "[REDACTED]"
    }


def test_response_facade_redacts_bearer_token_from_returned_envelope() -> None:
    # Given: an upstream envelope echoes a bearer token in every evidence field.
    credential = "unsafe-bearer-value"
    response = httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
            "warnings": [f"Bearer {credential}"],
            "infos": [f"token={credential}"],
            "diagnostics": {"authorization": credential},
        },
    )

    # When: the response crosses the compatibility facade.
    parsed = response_provenance(response, (credential,))

    # Then: no returned representation can expose the bearer value.
    assert credential not in repr(parsed)
    assert credential not in repr(parsed.envelope)
    assert credential not in repr(parsed.provenance)


def test_response_facade_redacts_assignment_credentials_from_all_evidence() -> None:
    # Given: hostile annotations contain assignments outside the bearer token.
    api_key = "warning-api-key"
    x_api_key = "info-x-api-key"
    client_value = "warning-client-secret"
    response = httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
            "warnings": [f"api_key={api_key}", f"client_secret={client_value}"],
            "infos": [f"x-api-key={x_api_key}"],
        },
    )

    # When: the response enters the Prometheus compatibility facade.
    parsed = response_provenance(response, ())

    # Then: no persisted or printable ingress evidence exposes those credential values.
    evidence = (
        json.dumps(parsed.provenance.body),
        repr(parsed),
        repr(parsed.envelope),
        repr(parsed.provenance),
    )
    for credential in (api_key, x_api_key, client_value):
        assert all(credential not in value for value in evidence)


@pytest.mark.parametrize(
    ("key", "separator"),
    [
        (key, separator)
        for key in (
            "authorization",
            "apikey",
            "xapikey",
            "accesstoken",
            "clientsecret",
            "token",
            "password",
            "secret",
        )
        for separator in ("=", ":")
    ]
    + [
        (key, separator)
        for key in (
            "api-key",
            "api key",
            "x-api-key",
            "x api key",
            "access-token",
            "access token",
            "client-secret",
            "client secret",
        )
        for separator in ("=", ":")
    ],
)
def test_response_facade_redacts_every_sensitive_assignment_key_and_separator(
    key: str, separator: str
) -> None:
    # Given: hostile warning and info text with a configured credential assignment.
    credential = f"unsafe-{key.replace(' ', '-')}-{separator}"
    warning = f"warning {key}{separator}{credential}"
    info = f"info {key}{separator}{credential}"
    response = httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
            "warnings": [warning],
            "infos": [info],
        },
    )

    # When: the text and complete response cross the ingress boundary.
    text = redact_text(warning, ())
    parsed = response_provenance(response, ())

    # Then: no returned provenance, body, or representation retains the value.
    evidence = (
        text,
        *parsed.provenance.warnings,
        *parsed.provenance.infos,
        json.dumps(parsed.provenance.body),
        repr(parsed),
    )
    assert all(credential not in value for value in evidence)


def test_response_facade_preserves_malformed_response_provenance() -> None:
    # Given: malformed bytes from the Prometheus HTTP boundary.
    response = httpx2.Response(502, content=b'{"status":"success"')

    # When: the established response facade parses the response.
    parsed = response_provenance(response, ())

    # Then: it retains status evidence without exposing an invalid body.
    assert parsed.provenance.status_code == 502
    assert parsed.provenance.body is None
    assert parsed.envelope is None


@pytest.mark.parametrize("scheme", ["Basic", "basic", "BASIC"])
def test_response_redacts_unconfigured_basic_credentials(scheme: str) -> None:
    # Given: an upstream echoes a Basic credential unrelated to configured auth.
    encoded = "YWxpY2U6cGFzc3cwcmQ="
    response = httpx2.Response(
        200,
        json={
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
            "warnings": [f"upstream used {scheme} {encoded}"],
            "infos": [f"Authorization: {scheme} {encoded}"],
        },
    )

    # When: the response crosses ingress without any configured secrets.
    parsed = response_provenance(response, ())

    # Then: generic header recognition still scrubs the encoded credentials.
    assert encoded not in repr(parsed)
    assert "[REDACTED]" in repr(parsed)
