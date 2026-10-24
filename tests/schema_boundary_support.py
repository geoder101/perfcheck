from __future__ import annotations

import json
from typing import TYPE_CHECKING, assert_never

from pydantic import JsonValue, TypeAdapter

if TYPE_CHECKING:
    from perfcheck.model_types import StrictModel


def mutated_json(
    model: StrictModel, path: tuple[str | int, ...], value: JsonValue
) -> str:
    payload = TypeAdapter[JsonValue](JsonValue).validate_json(model.model_dump_json())
    target: JsonValue = payload
    for key in path[:-1]:
        match key:
            case int():
                assert isinstance(target, list)
                target = target[key]
            case str():
                assert isinstance(target, dict)
                target = target[key]
            case _:
                assert_never(key)
    key = path[-1]
    match key:
        case int():
            assert isinstance(target, list)
            target[key] = value
        case str():
            assert isinstance(target, dict)
            target[key] = value
        case _:
            assert_never(key)
    return json.dumps(payload)
