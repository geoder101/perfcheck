from __future__ import annotations

import hashlib
from typing import Final

import pytest

from perfcheck.model_types import StrictModel
from perfcheck.storage import (
    artifact_content_sha256,
    canonical_json_bytes,
    policy_content_sha256,
)
from tests.cli_support import cli_policy, cli_run

POLICY_BYTES: Final = (
    b'{"algorithm_manifest":{"bootstrap":"pcg64-percentile-v1",'
    b'"eligibility":"trim-coverage-gap-v1","report":"canonical-json-markdown-v1",'
    b'"summary":"linear-quantile-v1"},"comparison_mode":"auto","metrics":['
    b'{"direction":"higher_is_worse","eligibility":{"cooldown_seconds":0,'
    b'"max_gap_steps":3,"min_analysis_window_seconds":300,'
    b'"min_coverage":0.80000000000000004,"min_points":20,"warmup_seconds":0},'
    b'"enabled":true,"expected_label_names":[],"metric_id":"latency",'
    b'"practical_threshold":0,"query":"latency_seconds","rate_window_seconds":60,'
    b'"statistic":"mean","step_seconds":15,"unit":"seconds"}],'
    b'"min_baseline_reference_runs":1,"min_baseline_runs":10,"min_current_runs":5,'
    b'"nominal_alpha":0.050000000000000003,"policy_id":"policy-1",'
    b'"prometheus_url":null,"schema_version":1,"suite_id":"suite-1"}\n'
)


class CanonicalProbe(StrictModel):
    z: tuple[float | bool | None, ...]
    a: str


@pytest.mark.parametrize(
    ("number", "encoded"),
    [(0.0, b"0"), (-0.0, b"0"), (0.1, b"0.10000000000000001"), (1e20, b"1e+20")],
)
def test_canonical_encoding_matches_explicit_bytes(
    number: float, encoded: bytes
) -> None:
    # Given: scalar variants, escaped text, and non-ASCII Unicode.
    probe = CanonicalProbe(z=(number, True, False, None), a='é\n"')
    expected = b'{"a":"\xc3\xa9\\n\\"","z":[' + encoded + b",true,false,null]}\n"
    # When: the canonical serializer renders the model.
    actual = canonical_json_bytes(probe)
    # Then: ordering, escaping, float precision, and the final newline are explicit.
    assert actual == expected


def test_policy_identity_matches_explicit_stdlib_sha256_oracle() -> None:
    # Given: an independently specified canonical policy, without its own hash.
    policy = cli_policy()
    expected = hashlib.sha256(POLICY_BYTES).hexdigest()
    # When: production calculates the policy identity.
    actual = policy_content_sha256(policy)
    # Then: neither the production serializer nor hasher supplies the oracle.
    assert actual == expected
    assert canonical_json_bytes(policy, omit_field="policy_sha256") == POLICY_BYTES
    assert (
        policy_content_sha256(policy.model_copy(update={"policy_sha256": "f" * 64}))
        == expected
    )


def test_artifact_identity_matches_explicit_stdlib_sha256_oracle() -> None:
    # Given: a schema-valid raw run reduced to one explicitly encoded sample.
    policy = cli_policy()
    raw = cli_run(policy, 1, 10.0)
    record = raw.metric_records[0]
    assert record.series is not None
    record = record.model_copy(
        update={
            "series": record.series.model_copy(
                update={"samples": record.series.samples[:1]}
            )
        }
    )
    raw = raw.model_copy(update={"metric_records": (record,)})
    policy_hash = hashlib.sha256(POLICY_BYTES).hexdigest().encode()
    embedded_policy = (
        POLICY_BYTES[:-2].replace(
            b'"policy_id":"policy-1",',
            b'"policy_id":"policy-1","policy_sha256":"' + policy_hash + b'",',
        )
        + b"}"
    )
    prefix = (
        b'{"artifact_type":"run",'
        b'"metadata":{"environment":"ci","git_sha":"abcdef","scenario":"baseline",'
        b'"target_topology":"single-node","test_name":"load-test"},'
        b'"metric_records":[{"availability":"available","failure":null,'
        b'"metric_id":"latency","provenance":{"end":"2026-01-01T01:10:00Z",'
        b'"endpoint_url":"https://metrics.example.test","http_status":null,'
        b'"prometheus_status":null,'
        b'"query":"latency_seconds","request_path":"/api/v1/query_range",'
        b'"start":"2026-01-01T01:00:00Z","step_seconds":15},'
        b'"series":{"labels":[],"metric_id":"latency","samples":['
        b'{"timestamp":"2026-01-01T01:00:00Z","value":10}]}}],'
        b'"policy_sha256":"'
    )
    suffix = (
        b',"run_id":"run-1","schema_version":1,"source_interval":{'
        b'"end":"2026-01-01T01:10:00Z","start":"2026-01-01T01:00:00Z"},'
        b'"suite_id":"suite-1"}\n'
    )
    expected_bytes = (
        prefix + policy_hash + b'","policy_snapshot":' + embedded_policy + suffix
    )
    # When: the artifact's self-referential identity is calculated.
    actual = artifact_content_sha256(raw)
    # Then: the independent bytes pin nested policy inclusion and hash exclusion.
    assert canonical_json_bytes(raw, omit_field="content_sha256") == expected_bytes
    assert actual == hashlib.sha256(expected_bytes).hexdigest()
    assert (
        artifact_content_sha256(raw.model_copy(update={"content_sha256": "f" * 64}))
        == actual
    )
