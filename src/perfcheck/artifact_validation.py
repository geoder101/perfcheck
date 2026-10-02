"""Shared strict validators for persisted artifact values."""

from datetime import datetime, timedelta
from typing import Final

from perfcheck.errors import ArtifactSchemaCode, ArtifactSchemaError

_SECRET_MARKERS: Final = (
    "access_token=",
    "api_key=",
    "authorization:",
    "bearer ",
    "password=",
    "token=",
)
def validate_utc(value: datetime) -> datetime:
    """Require an RFC-3339 instant in UTC."""
    if value.utcoffset() != timedelta(0):
        raise ArtifactSchemaError(ArtifactSchemaCode.NON_UTC_TIMESTAMP)
    return value


def validate_interval(start: datetime, end: datetime) -> None:
    """Require a positive interval."""
    if end <= start:
        raise ArtifactSchemaError(ArtifactSchemaCode.INVALID_INTERVAL)


def contains_secret(value: str) -> bool:
    """Identify persisted strings that would expose request credentials."""
    return any(marker in value.casefold() for marker in _SECRET_MARKERS)
