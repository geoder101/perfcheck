"""Loopback-only deterministic Prometheus fixture for executable examples."""

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
    """Validated deterministic data for the local Prometheus mock."""

    model_config: ClassVar[ConfigDict] = ConfigDict(frozen=True)

    sample_count: int = Field(default=41, ge=20)
    queries: dict[str, tuple[float, ...]]


class FixtureArguments(argparse.Namespace):
    """Typed command-line arguments for the standalone fixture server."""

    port: int = 0
    fixture: Path = Path()


def _handler(fixture: PrometheusFixture) -> type[BaseHTTPRequestHandler]:
    positions: dict[str, int] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            """Return fixture readiness only from its local health endpoint."""
            if self.path == "/healthz":
                self._send(HTTPStatus.OK, {"status": "ok"})
                return
            self._send(HTTPStatus.NOT_FOUND, {"status": "not found"})

        def do_POST(self) -> None:
            """Return one deterministic matrix or reject an unknown query."""
            if self.path != "/api/v1/query_range":
                self._send(HTTPStatus.NOT_FOUND, {"status": "error"})
                return
            values = parse_qs(self.rfile.read(self._content_length()).decode())
            query = values.get("query", [""])[0]
            start = values.get("start", [""])[0]
            response_values = fixture.queries.get(query)
            if response_values is None:
                self._send(HTTPStatus.BAD_REQUEST, {"status": "error"})
                return
            position = positions.get(query, 0)
            positions[query] = position + 1
            value = response_values[min(position, len(response_values) - 1)]
            start_timestamp = datetime.fromisoformat(start).timestamp()
            self._send(
                HTTPStatus.OK,
                {
                    "status": "success",
                    "data": {
                        "resultType": "matrix",
                        "result": [
                            {
                                "metric": {},
                                "values": [
                                    [start_timestamp + (15 * index), str(value)]
                                    for index in range(fixture.sample_count)
                                ],
                            }
                        ],
                    },
                },
            )

        def _content_length(self) -> int:
            return int(self.headers.get("Content-Length", "0"))

        def _send(self, status: HTTPStatus, payload: dict[str, JsonValue]) -> None:
            encoded = json.dumps(payload, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", _CONTENT_TYPE)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            _ = self.wfile.write(encoded)

        @override
        def log_message(self, format: str, *_args: str) -> None:
            """Suppress request logs so fixture output never carries request secrets."""
            del format, _args

    return Handler


def main() -> None:
    """Start a loopback-only fixture on the selected ephemeral port."""
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--port", type=int, required=True)
    _ = parser.add_argument("--fixture", type=Path, required=True)
    arguments = FixtureArguments()
    _ = parser.parse_args(namespace=arguments)
    fixture = PrometheusFixture.model_validate_json(arguments.fixture.read_bytes())
    address = ("127.0.0.1", arguments.port)
    with ThreadingHTTPServer(address, _handler(fixture)) as server:
        print(f"http://127.0.0.1:{server.server_port}", flush=True)  # noqa: T201
        server.serve_forever()


if __name__ == "__main__":
    main()
