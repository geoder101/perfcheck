from __future__ import annotations

import logging

import anyio
import httpx2
import pytest

from perfcheck.collection_service import create_collection_client


@pytest.mark.parametrize("case", [(200, False), (503, False), (200, True), (503, True)])
def test_factory_hooks_log_useful_metadata_without_secrets(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    case: tuple[int, bool],
) -> None:
    # Given: secrets in every request surface and in response headers and body.
    status_code, bearer_auth = case
    secrets = (
        "path-secret-71",
        "query-secret-72",
        "user-secret-73",
        "password-secret-74",
        "bearer-secret-75",
        "header-secret-76",
        "body-secret-77",
        "response-header-secret-78",
        "response-body-secret-79",
    )
    observed: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        observed.append(request)
        return httpx2.Response(
            status_code,
            headers={"X-Api-Key": secrets[7]},
            content=secrets[8].encode(),
        )

    async def scenario() -> None:
        async with httpx2.MockTransport(respond) as transport:

            async def send(
                self: httpx2.AsyncHTTPTransport, request: httpx2.Request
            ) -> httpx2.Response:
                del self
                return await transport.handle_async_request(request)

            monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", send)
            async with create_collection_client() as client:
                credentials = "" if bearer_auth else f"{secrets[2]}:{secrets[3]}@"
                headers = {"X-Api-Key": secrets[5], "X-Token": secrets[4]}
                if bearer_auth:
                    headers["Authorization"] = f"Bearer {secrets[4]}"
                origin = f"https://{credentials}prometheus.example"
                url = f"{origin}/{secrets[0]}?token={secrets[1]}"
                _ = await client.post(
                    url,
                    headers=headers,
                    content=f"query={secrets[6]}&token={secrets[4]}",
                )

    # When: the real factory's installed request and response hooks run.
    with caplog.at_level(logging.INFO, logger="perfcheck.collection_service"):
        anyio.run(scenario)

    # Then: both hooks retain useful metadata but none of the sensitive surfaces.
    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "perfcheck.collection_service"
    ]
    assert len(messages) == 2
    request_log, response_log = messages
    assert "request" in request_log.lower()
    assert "response" in response_log.lower()
    for message in messages:
        assert "POST" in message
        assert "prometheus.example" in message
        assert all(secret not in message for secret in secrets)
        assert all(
            field not in message.lower()
            for field in ("authorization", "basic ", "bearer ", "x-api-key", "token=")
        )
    assert str(status_code) in response_log
    assert len(observed) == 1
    authorization = observed[0].headers["Authorization"]
    assert authorization.startswith("Bearer " if bearer_auth else "Basic ")
    assert all(authorization not in message for message in messages)
    assert observed[0].url.path == f"/{secrets[0]}"
    assert secrets[1] in str(observed[0].url)
    assert secrets[6].encode() in observed[0].content
