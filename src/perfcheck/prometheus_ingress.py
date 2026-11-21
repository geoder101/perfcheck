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
_BASIC_VALUE: Final = re.compile(r"(?i)\bbasic\s+[a-z0-9+/]+={0,2}")
_ASSIGNMENT_CREDENTIAL_VALUE: Final = re.compile(
    r"""(?ix)
    \b(
        (?:
            authorization | x[-_ ]?api[-_ ]?key | api[-_ ]?key |
            access[-_ ]?token | client[-_ ]?secret | token | password | secret
        )
        \s*[:=]\s*
    )
    [^\s,;]+
    """
)
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


def response_provenance(
    response: httpx2.Response, secrets: tuple[str, ...]
) -> ParsedResponse:
    """Parse response bytes once into strict models and sanitized provenance."""
    try:
        envelope = PrometheusEnvelopeIngress.model_validate_json(response.content)
    except ValidationError:
        return ParsedResponse(
            ResponseProvenance(response.status_code, None, (), ()), None
        )
    body = redact_json(envelope.model_dump(mode="json", by_alias=True), secrets)
    envelope = PrometheusEnvelopeIngress.model_validate_json(
        json.dumps(body, separators=(",", ":"))
    )
    return ParsedResponse(
        ResponseProvenance(
            response.status_code,
            body,
            tuple(redact_text(warning, secrets) for warning in envelope.warnings),
            tuple(redact_text(info, secrets) for info in envelope.infos),
        ),
        envelope,
    )


def redact_text(value: str, secrets: tuple[str, ...]) -> str:
    """Replace known credential values in hostile text."""
    secret_safe = value
    for secret in secrets:
        if secret:
            secret_safe = secret_safe.replace(secret, _REDACTED)
    bearer_safe = _BEARER_VALUE.sub(f"Bearer {_REDACTED}", secret_safe)
    basic_safe = _BASIC_VALUE.sub(f"Basic {_REDACTED}", bearer_safe)
    return _ASSIGNMENT_CREDENTIAL_VALUE.sub(rf"\1{_REDACTED}", basic_safe)


def redact_json(value: JsonValue, secrets: tuple[str, ...]) -> JsonValue:
    """Recursively remove credential keys and bearer values from hostile JSON."""
    match value:
        case str() as text:
            return redact_text(text, secrets)
        case list() as values:
            return [redact_json(item, secrets) for item in values]
        case dict() as mapping:
            return {
                _redacted_key(key, secrets): _REDACTED
                if _is_sensitive_key(key)
                else redact_json(item, secrets)
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


def _redacted_key(key: str, secrets: tuple[str, ...]) -> str:
    return _REDACTED if _is_sensitive_key(key) else redact_text(key, secrets)
