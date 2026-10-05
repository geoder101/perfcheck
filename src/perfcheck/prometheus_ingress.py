"""Prometheus response parsing and secret-safe evidence normalization."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Literal, Self, assert_never

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    RootModel,
    ValidationError,
    model_validator,
)
from pydantic_core import PydanticCustomError

if TYPE_CHECKING:
    import httpx2

from perfcheck.prometheus_types import ResponseProvenance

_REDACTED: Final = "[REDACTED]"
_SENSITIVE_KEY_NAMES: Final = frozenset(
    {
        "authorization",
        "apikey",
        "xapikey",
        "accesstoken",
        "clientsecret",
        "token",
        "password",
        "secret",
    }
)
_BEARER_VALUE: Final = re.compile(r"(?i)\bbearer\s+[^\s,;]+")
_MISSING_MATRIX_DATA_CODE: Final = "missing_matrix_data"
_MISSING_MATRIX_DATA_MESSAGE: Final = "successful Prometheus responses require data"
_STRICT_IGNORE_CONFIG: Final = ConfigDict(strict=True, frozen=True, extra="ignore")


class MatrixSampleIngress(RootModel[tuple[int | float, str]]):
    """One exact Prometheus matrix sample at the ingress boundary."""

    model_config: ClassVar[ConfigDict] = ConfigDict(strict=True, frozen=True)


class MatrixSeriesIngress(BaseModel):
    """One matrix series with its dynamic string label map."""

    model_config: ClassVar[ConfigDict] = _STRICT_IGNORE_CONFIG

    metric: dict[str, str]
    values: tuple[MatrixSampleIngress, ...]
    histograms: tuple[JsonValue, ...] | None = None


class MatrixDataIngress(BaseModel):
    """Typed matrix payload fields retained from the upstream response."""

    model_config: ClassVar[ConfigDict] = _STRICT_IGNORE_CONFIG

    result_type: str = Field(alias="resultType")
    result: tuple[MatrixSeriesIngress, ...]


class PrometheusEnvelopeIngress(BaseModel):
    """Prometheus response envelope with explicitly typed nested boundaries."""

    model_config: ClassVar[ConfigDict] = _STRICT_IGNORE_CONFIG

    status: Literal["success", "error"]
    data: MatrixDataIngress | None = None
    warnings: tuple[str, ...] = ()
    infos: tuple[str, ...] = ()
    diagnostics: JsonValue | None = None

    @model_validator(mode="after")
    def require_matrix_data(self) -> Self:
        """Require matrix data for successful API envelopes."""
        if self.status == "success" and self.data is None:
            raise PydanticCustomError(
                _MISSING_MATRIX_DATA_CODE, _MISSING_MATRIX_DATA_MESSAGE
            )
        return self


@dataclass(frozen=True, slots=True)
class ParsedResponse:
    """Sanitized response evidence paired with parsed ingress data."""

    provenance: ResponseProvenance
    envelope: PrometheusEnvelopeIngress | None


def response_provenance(response: httpx2.Response, token: str | None) -> ParsedResponse:
    """Parse response bytes once into strict models and sanitized provenance."""
    try:
        envelope = PrometheusEnvelopeIngress.model_validate_json(response.content)
    except ValidationError:
        return ParsedResponse(
            ResponseProvenance(response.status_code, None, (), ()), None
        )
    body = redact_json(envelope.model_dump(mode="json", by_alias=True), token)
    envelope = PrometheusEnvelopeIngress.model_validate_json(
        json.dumps(body, separators=(",", ":"))
    )
    return ParsedResponse(
        ResponseProvenance(
            response.status_code,
            body,
            tuple(redact_text(warning, token) for warning in envelope.warnings),
            tuple(redact_text(info, token) for info in envelope.infos),
        ),
        envelope,
    )


def redact_text(value: str, token: str | None) -> str:
    """Replace known bearer values and literal bearer credentials in hostile text."""
    token_safe = value.replace(token, _REDACTED) if token else value
    return _BEARER_VALUE.sub(f"Bearer {_REDACTED}", token_safe)


def redact_json(value: JsonValue, token: str | None) -> JsonValue:
    """Recursively remove credential keys and bearer values from hostile JSON."""
    match value:
        case str() as text:
            return redact_text(text, token)
        case list() as values:
            return [redact_json(item, token) for item in values]
        case dict() as mapping:
            return {
                _redacted_key(key, token): _REDACTED
                if _is_sensitive_key(key)
                else redact_json(item, token)
                for key, item in mapping.items()
            }
        case None | bool() | int() | float():
            return value
        case _:
            assert_never(value)


def _is_sensitive_key(key: str) -> bool:
    normalized_key = "".join(
        character for character in key.casefold() if character.isalnum()
    )
    return normalized_key in _SENSITIVE_KEY_NAMES


def _redacted_key(key: str, token: str | None) -> str:
    return _REDACTED if _is_sensitive_key(key) else redact_text(key, token)
