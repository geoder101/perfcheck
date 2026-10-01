from typer.testing import CliRunner

from perfcheck import perfcheck
from perfcheck.cli import app


def test_public_import_and_cli_help() -> None:
    # Given: the public library export and installed-command application.
    # When: the CLI help is invoked.
    result = CliRunner().invoke(app, ["--help"])

    # Then: the public export is the command application and help succeeds.
    assert perfcheck is app
    assert result.exit_code == 0
    assert "Usage:" in result.output
