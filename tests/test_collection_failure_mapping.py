from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path  # noqa: TC003 - pytest resolves fixture annotations.
from typing import TYPE_CHECKING, Final

import httpx2
import pytest

from perfcheck.model_types import CollectionFailureReason, MetricAvailability
from perfcheck.prometheus_types import FailureKind
from perfcheck.run_models import RunArtifact
from perfcheck.storage import load_artifact
from tests.collection_failure_support import (
    SECRET,
    START,
    collect_cli,
    failure_policy,
    install_transport,
    matrix_response,
)

if TYPE_CHECKING:
    from pydantic import JsonValue


@dataclass(frozen=True, slots=True)
class FailureCase:
    kind: FailureKind
    reason: CollectionFailureReason
    payload: JsonValue = None
    status: int = 200


_CASES: Final = (
    FailureCase(FailureKind.TIMEOUT, CollectionFailureReason.TIMEOUT),
    FailureCase(FailureKind.TRANSPORT, CollectionFailureReason.TRANSPORT_ERROR),
    FailureCase(
        FailureKind.HTTP_ERROR, CollectionFailureReason.TRANSPORT_ERROR, status=503
    ),
    FailureCase(
        FailureKind.API_ERROR,
        CollectionFailureReason.INVALID_RESPONSE,
        {"status": "error", "errorType": "execution", "error": SECRET},
    ),
    FailureCase(
        FailureKind.MALFORMED_RESPONSE, CollectionFailureReason.INVALID_RESPONSE
    ),
    FailureCase(
        FailureKind.RESULT_TYPE,
        CollectionFailureReason.INVALID_RESPONSE,
        {"status": "success", "data": {"resultType": "vector", "result": []}},
    ),
    FailureCase(
        FailureKind.EMPTY_SERIES,
        CollectionFailureReason.NO_SERIES,
        {"status": "success", "data": {"resultType": "matrix", "result": []}},
    ),
    FailureCase(
        FailureKind.MULTIPLE_SERIES,
        CollectionFailureReason.MULTIPLE_SERIES,
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {"metric": {}, "values": [[START, "1"]]},
                    {"metric": {}, "values": [[START, "2"]]},
                ],
            },
        },
    ),
    FailureCase(
        FailureKind.UNEXPECTED_LABELS,
        CollectionFailureReason.UNEXPECTED_LABELS,
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {"metric": {"job": "unexpected"}, "values": [[START, "1"]]},
                ],
            },
        },
    ),
    FailureCase(
        FailureKind.HISTOGRAM_SAMPLE,
        CollectionFailureReason.INVALID_RESPONSE,
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {},
                        "values": [],
                        "histograms": [[START, {"count": "1"}]],
                    },
                ],
            },
        },
    ),
    FailureCase(
        FailureKind.NONFINITE_SAMPLE,
        CollectionFailureReason.NONFINITE_VALUE,
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {"metric": {}, "values": [[START, "NaN"]]},
                ],
            },
        },
    ),
    FailureCase(
        FailureKind.DUPLICATE_TIMESTAMP,
        CollectionFailureReason.INVALID_RESPONSE,
        {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {"metric": {}, "values": [[START, "1"], [START, "2"]]},
                ],
            },
        },
    ),
)


@pytest.mark.parametrize("case", _CASES, ids=[case.kind.value for case in _CASES])
def test_reachable_failure_is_persisted_with_healthy_sibling(
    case: FailureCase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Given: an actual wire failure alongside a complete healthy matrix.
    def fail(request: httpx2.Request) -> httpx2.Response:
        exception_type = {
            FailureKind.TIMEOUT: httpx2.ReadTimeout,
            FailureKind.TRANSPORT: httpx2.ConnectError,
        }.get(case.kind)
        if exception_type is not None:
            raise exception_type(SECRET, request=request)
        return httpx2.Response(
            case.status, json=case.payload, headers={"X-Detail": SECRET}
        )

    install_transport(monkeypatch, fail)

    # When: the real CLI collects and persists the run.
    result = collect_cli(tmp_path, failure_policy())

    # Then: the exact reason/status survives, but response secrets do not.
    assert result.exit_code == 4, result.output
    raw = load_artifact(tmp_path / "raw.json")
    assert isinstance(raw, RunArtifact)
    healthy, failed = raw.metric_records
    assert failed.availability is MetricAvailability.UNAVAILABLE
    assert failed.series is None
    assert failed.failure is not None
    assert failed.failure.reason is case.reason
    assert failed.failure.detail == f"Prometheus collection failed: {case.kind}"
    assert failed.provenance.http_status == (
        None
        if case.kind in {FailureKind.TIMEOUT, FailureKind.TRANSPORT}
        else case.status
    )
    assert healthy.availability is MetricAvailability.AVAILABLE
    assert healthy.series is not None
    assert len(healthy.series.samples) == 41
    assert {sample.value for sample in healthy.series.samples} == {2.5}
    assert SECRET not in (tmp_path / "raw.json").read_text() + result.output


@pytest.mark.parametrize(
    ("values", "reason"),
    [
        ([], CollectionFailureReason.NO_SERIES),
        ([[START + 15, "1"], [START, "2"]], CollectionFailureReason.INVALID_RESPONSE),
        ([[1e20, "1"]], CollectionFailureReason.INVALID_RESPONSE),
    ],
    ids=["empty-samples", "descending-samples", "unrepresentable-timestamp"],
)
def test_unpersistable_samples_remain_partial_failures(
    values: JsonValue,
    reason: CollectionFailureReason,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: ingress-valid matrix samples that cannot form valid raw evidence.
    install_transport(monkeypatch, lambda _: matrix_response(values))

    # When: collection converts the wire evidence into the persisted run.
    result = collect_cli(tmp_path, failure_policy())

    # Then: invalid samples cannot discard the healthy sibling or abort persistence.
    assert result.exit_code == 4, repr(result.exception)
    raw = load_artifact(tmp_path / "raw.json")
    assert isinstance(raw, RunArtifact)
    healthy, failed = raw.metric_records
    assert healthy.series is not None
    assert len(healthy.series.samples) == 41
    assert failed.availability is MetricAvailability.UNAVAILABLE
    assert failed.failure is not None
    assert failed.failure.reason is reason
    assert failed.provenance.http_status == 200
