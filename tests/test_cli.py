from unittest.mock import patch

from click.testing import CliRunner

from bot.cli import cli
from bot.orchestrator import CallResult


def _ok_result(scenario_id="simple_scheduling_new_patient"):
    return CallResult(
        call_id=f"{scenario_id}-abcd1234",
        scenario_id=scenario_id,
        call_sid="CA123",
        status="completed",
        duration_seconds=90,
        recording_path="data/calls/x/recording.mp3",
        transcript_path="data/calls/x/transcript.json",
    )


def test_list_scenarios_prints_every_scenario():
    runner = CliRunner()
    result = runner.invoke(cli, ["list-scenarios"])
    assert result.exit_code == 0
    assert "simple_scheduling_new_patient" in result.output
    assert "[scheduling]" in result.output


def test_call_command_success(settings_env):
    runner = CliRunner()
    with patch("bot.cli.run_call", return_value=_ok_result()):
        result = runner.invoke(cli, ["call", "--scenario", "simple_scheduling_new_patient"])
    assert result.exit_code == 0
    assert "OK" in result.output


def test_call_command_unknown_scenario_errors(settings_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["call", "--scenario", "not-a-real-scenario"])
    assert result.exit_code != 0


def test_call_command_json_output(settings_env):
    runner = CliRunner()
    with patch("bot.cli.run_call", return_value=_ok_result()):
        result = runner.invoke(cli, ["call", "--scenario", "simple_scheduling_new_patient", "--json"])
    assert result.exit_code == 0
    assert '"status": "completed"' in result.output


def test_run_batch_command_limits_to_requested_scenarios(settings_env):
    runner = CliRunner()
    with patch("bot.cli.run_batch", return_value=[_ok_result()]) as mock_batch:
        result = runner.invoke(
            cli,
            ["run-batch", "--scenario", "simple_scheduling_new_patient"],
        )
    assert result.exit_code == 0
    scenarios_arg = mock_batch.call_args[0][0]
    assert [s.id for s in scenarios_arg] == ["simple_scheduling_new_patient"]


def test_run_batch_command_unknown_scenario_errors(settings_env):
    runner = CliRunner()
    result = runner.invoke(cli, ["run-batch", "--scenario", "does-not-exist"])
    assert result.exit_code != 0


def test_run_batch_command_fails_when_any_call_fails(settings_env):
    failed = CallResult(
        call_id="c", scenario_id="s", call_sid=None, status="error",
        duration_seconds=None, recording_path=None, transcript_path=None, error="boom",
    )
    runner = CliRunner()
    with patch("bot.cli.run_batch", return_value=[failed]):
        result = runner.invoke(cli, ["run-batch"])
    assert result.exit_code != 0
