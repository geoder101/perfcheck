from __future__ import annotations

import json
import runpy
import sys
from typing import TYPE_CHECKING

import pytest
from pydantic import TypeAdapter

if TYPE_CHECKING:
    from pathlib import Path

from perfcheck.policy_models import SuitePolicy


def test_basedpyright_rejects_cross_domain_identifier_interchange(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    # Given: distinct policy and metric identities at the public model boundary.
    probe = tmp_path / "cross_domain_identifiers.py"
    _ = probe.write_text(
        """from perfcheck.model_types import Direction, MetricUnit, Statistic
from perfcheck.model_types import PolicyId
from perfcheck.policy_models import MetricPolicy

wrong_metric = MetricPolicy(
    metric_id=PolicyId('policy-1'),
    query='latency_seconds',
    unit=MetricUnit.SECONDS,
    direction=Direction.HIGHER_IS_WORSE,
    statistic=Statistic.MEAN,
    practical_threshold=0.0,
    step_seconds=15,
    rate_window_seconds=60,
)

""",
        encoding="utf-8",
    )

    # When: the strict type checker analyzes an attempted domain interchange.
    monkeypatch.setattr(sys, "argv", ["basedpyright", str(probe)])
    with pytest.raises(SystemExit) as exit_result:
        _ = runpy.run_module("basedpyright.__main__", run_name="__main__")

    # Then: the interchange is rejected statically rather than at runtime.
    assert exit_result.value.code != 0


def test_production_identity_annotations_preserve_string_wire_contract() -> None:
    # Given: raw JSON policy input at the public Pydantic boundary.
    payload = {
        "policy_id": "policy-1",
        "suite_id": "suite-1",
        "policy_sha256": "0" * 64,
        "metrics": [
            {
                "metric_id": "latency",
                "query": "latency_seconds",
                "unit": "seconds",
                "direction": "higher_is_worse",
                "statistic": "mean",
                "practical_threshold": 0.0,
                "step_seconds": 15,
                "rate_window_seconds": 60,
            }
        ],
    }

    # When: the public model parses and serializes the valid wire representation.
    policy = SuitePolicy.model_validate_json(json.dumps(payload))
    schema = SuitePolicy.model_json_schema()

    # Then: production annotations have distinct domains while JSON remains strings.
    identifier_adapter = TypeAdapter(dict[str, str])
    identifier_schema = identifier_adapter.validate_python(
        schema["$defs"]["PolicyIdentifier"]
    )
    if "$ref" in identifier_schema:
        _, definitions_key, identifier_key = identifier_schema["$ref"].split("/")
        identifier_schema = identifier_adapter.validate_python(
            schema[definitions_key][identifier_key]
        )
    assert identifier_schema["type"] == "string"
    assert identifier_schema["pattern"] == r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"
    assert policy.model_dump(mode="json")["policy_id"] == "policy-1"
