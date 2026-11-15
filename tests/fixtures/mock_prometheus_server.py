#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.14,<3.15"
# dependencies = ["pydantic>=2.12"]
# ///

# ─── How to run ───
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly:
#      uv run tests/fixtures/mock_prometheus_server.py --port 18090 \
#        --fixture tests/fixtures/prometheus/matrix.json
# ──────────────────

from __future__ import annotations

import argparse
import json
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, Final, override
from urllib.parse import parse_qs

from pydantic import BaseModel, ConfigDict, Field, JsonValue

_CONTENT_TYPE: Final = "application/json"


class PrometheusFixture(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    sample_count: int = Field(default=41, ge=20)
    queries: dict[str, tuple[float, ...]]


class FixtureArguments(argparse.Namespace):
    port: int = 0
    fixture: Path = Path()
    echo_token_body: str | None = None
    echo_basic_body: str | None = None


def _handler(
    fixture: PrometheusFixture,
    echo_token: str | None,
    echo_basic: str | None,
) -> type[BaseHTTPRequestHandler]:
    positions: dict[str, int] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/healthz":
                self._send(HTTPStatus.OK, {"status": "ok"})
                return
            self._send(HTTPStatus.NOT_FOUND, {"status": "not found"})

        def do_POST(self) -> None:
            if self.path != "/api/v1/query_range":
                self._send(HTTPStatus.NOT_FOUND, {"status": "error"})
                return
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length).decode()
            values = parse_qs(body).get("query", [])
            query = values[0] if values else ""
            start_values = parse_qs(body).get("start", [])
            start = start_values[0] if start_values else ""
            response_values = fixture.queries.get(query)
            if response_values is None:
                self._send(HTTPStatus.BAD_REQUEST, {"status": "error"})
                return
            position = positions.get(query, 0)
            positions[query] = position + 1
            value = response_values[min(position, len(response_values) - 1)]
            response: dict[str, JsonValue] = {
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [
                        {
                            "metric": {},
                            "values": [
                                [
                                    datetime.fromisoformat(start).timestamp()
                                    + (15 * index),
                                    str(value),
                                ]
                                for index in range(fixture.sample_count)
                            ],
                        }
                    ],
                },
            }
            if echo_token is not None:
                response["warnings"] = [f"api_key={echo_token}"]
                response["infos"] = [f"x-api-key={echo_token}"]
            if echo_basic is not None:
                username, _, password = echo_basic.partition(":")
                response["warnings"] = [
                    f"api_key={username}",
                    f"api_key={password}",
                ]
                response["infos"] = [
                    f"x-api-key={username}",
                    f"x-api-key={password}",
                ]
            self._send(HTTPStatus.OK, response)

        def _send(self, status: HTTPStatus, payload: dict[str, JsonValue]) -> None:
            encoded = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", _CONTENT_TYPE)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            _ = self.wfile.write(encoded)

        @override
        def log_message(self, format: str, *_args: str) -> None:
            del format, _args

    return Handler


def main() -> None:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--port", type=int, required=True)
    _ = parser.add_argument("--fixture", type=Path, required=True)
    _ = parser.add_argument("--echo-token-body")
    _ = parser.add_argument("--echo-basic-body")
    arguments = FixtureArguments()
    _ = parser.parse_args(namespace=arguments)
    fixture = PrometheusFixture.model_validate_json(arguments.fixture.read_bytes())
    with ThreadingHTTPServer(
        (
            "127.0.0.1",
            arguments.port,
        ),
        _handler(fixture, arguments.echo_token_body, arguments.echo_basic_body),
    ) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)  # noqa: T201
        server.serve_forever()


if __name__ == "__main__":
    main()
