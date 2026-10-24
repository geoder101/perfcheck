import pytest

from perfcheck.cli_services import CliInputCode, CliInputError
from perfcheck.collection_service import CollectionInputCode, CollectionInputError


@pytest.mark.parametrize("code", list(CliInputCode))
def test_cli_input_error_renders_code_value(code: CliInputCode) -> None:
    # Given: a command input error constructed with a declared diagnostic code.
    error = CliInputError(code)

    # When: the error is rendered as text.
    rendered = str(error)

    # Then: the text is exactly the stable code value.
    assert rendered == code.value


@pytest.mark.parametrize("code", list(CollectionInputCode))
def test_collection_input_error_renders_code_value(code: CollectionInputCode) -> None:
    # Given: a collection input error constructed with a declared diagnostic code.
    error = CollectionInputError(code)

    # When: the error is rendered as text.
    rendered = str(error)

    # Then: the text is exactly the stable code value.
    assert rendered == code.value
