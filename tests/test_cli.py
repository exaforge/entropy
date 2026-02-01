"""CLI smoke tests using typer's CliRunner."""

from typer.testing import CliRunner

from entropy.cli.app import app

runner = CliRunner()


class TestConfigCommand:
    """Tests for the config command."""

    def test_config_show(self):
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "Pipeline" in result.output
        assert "Simulation" in result.output

    def test_config_set_invalid_key(self):
        result = runner.invoke(app, ["config", "set", "invalid.key", "value"])
        assert result.exit_code == 1
        assert "Unknown key" in result.output

    def test_config_set_invalid_int_value(self):
        result = runner.invoke(app, ["config", "set", "simulation.rate_tier", "abc"])
        assert result.exit_code == 1
        assert "Invalid integer" in result.output

    def test_config_set_missing_args(self):
        result = runner.invoke(app, ["config", "set"])
        assert result.exit_code == 1

    def test_config_unknown_action(self):
        result = runner.invoke(app, ["config", "unknown_action"])
        assert result.exit_code == 1
        assert "Unknown action" in result.output


class TestValidateCommand:
    """Tests for the validate command."""

    def test_validate_nonexistent_file(self):
        result = runner.invoke(app, ["validate", "/nonexistent/path.yaml"])
        assert result.exit_code != 0


class TestVersionFlag:
    """Test the --version flag."""

    def test_version_output(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "entropy" in result.output
