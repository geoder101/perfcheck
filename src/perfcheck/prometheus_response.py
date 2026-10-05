"""Compatibility facade for Prometheus response parsing and validation."""

from perfcheck.prometheus_ingress import redact_json, redact_text, response_provenance
from perfcheck.prometheus_validation import classify_success

__all__ = [
    "classify_success",
    "redact_json",
    "redact_text",
    "response_provenance",
]
