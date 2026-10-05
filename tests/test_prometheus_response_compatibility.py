from __future__ import annotations

import httpx2

from perfcheck.prometheus_response import redact_json, response_provenance


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
    parsed = response_provenance(response, "top-secret")

    # Then: its public helpers retain the secret-safe compatibility contract.
    assert parsed.provenance.status_code == 200
    assert parsed.provenance.warnings == ("Bearer [REDACTED]",)
    assert redact_json({"authorization": "top-secret"}, "top-secret") == {
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
    parsed = response_provenance(response, credential)

    # Then: no returned representation can expose the bearer value.
    assert credential not in repr(parsed)
    assert credential not in repr(parsed.envelope)
    assert credential not in repr(parsed.provenance)


def test_response_facade_preserves_malformed_response_provenance() -> None:
    # Given: malformed bytes from the Prometheus HTTP boundary.
    response = httpx2.Response(502, content=b'{"status":"success"')

    # When: the established response facade parses the response.
    parsed = response_provenance(response, None)

    # Then: it retains status evidence without exposing an invalid body.
    assert parsed.provenance.status_code == 502
    assert parsed.provenance.body is None
    assert parsed.envelope is None
