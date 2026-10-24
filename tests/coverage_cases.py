from typing import Literal, assert_never


def exhaustive(value: Literal["first", "second"]) -> int:
    match value:
        case "first":
            return 1
        case "second":
            return 2
        case _:
            assert_never(value)


def fallback(value: int) -> int:
    match value:
        case 1:
            return 1
        case _:
            return 0


def validate(value: int) -> int:
    if value < 0:
        message = "value must be nonnegative"
        raise ValueError(message)
    return value


def default_pragma(value: bool) -> int:
    if value:  # pragma: no cover
        return 1
    return 0
