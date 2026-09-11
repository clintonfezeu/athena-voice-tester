import json
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


def test_analyze_all_skips_calls_without_transcript(settings_env, tmp_path, monkeypatch):
    import bot.cli as cli_module

    monkeypatch.setattr(cli_module, "CALLS_DIR", tmp_path)
    (tmp_path / "no-transcript-call").mkdir()

    runner = CliRunner()
    result = runner.invoke(cli, ["analyze-all"])
    assert result.exit_code == 0
    assert "Analyzed 0 call(s)." in result.output


def test_analyze_all_analyzes_calls_with_transcript(settings_env, tmp_path, monkeypatch):
    import bot.cli as cli_module

    monkeypatch.setattr(cli_module, "CALLS_DIR", tmp_path)
    call_dir = tmp_path / "simple_scheduling_new_patient-abcd1234"
    call_dir.mkdir()
    (call_dir / "transcript.json").write_text(
        json.dumps({"call_id": "x", "scenario_id": "simple_scheduling_new_patient", "turns": []}),
        encoding="utf-8",
    )
    (call_dir / "metadata.json").write_text(
        json.dumps({"scenario_id": "simple_scheduling_new_patient"}), encoding="utf-8"
    )

    runner = CliRunner()
    with patch("bot.cli.analyze_and_save") as mock_analyze:
        result = runner.invoke(cli, ["analyze-all"])

    assert result.exit_code == 0
    assert mock_analyze.called
    assert "Analyzed 1 call(s)." in result.output


def test_analyze_all_skips_already_analyzed_unless_forced(settings_env, tmp_path, monkeypatch):
    import bot.cli as cli_module

    monkeypatch.setattr(cli_module, "CALLS_DIR", tmp_path)
    call_dir = tmp_path / "c1"
    call_dir.mkdir()
    (call_dir / "transcript.json").write_text(
        json.dumps({"call_id": "x", "scenario_id": "simple_scheduling_new_patient", "turns": []}),
        encoding="utf-8",
    )
    (call_dir / "findings.json").write_text("[]", encoding="utf-8")

    runner = CliRunner()
    with patch("bot.cli.analyze_and_save") as mock_analyze:
        result = runner.invoke(cli, ["analyze-all"])
    assert not mock_analyze.called
    assert "Analyzed 0 call(s)." in result.output

    with patch("bot.cli.analyze_and_save") as mock_analyze:
        result = runner.invoke(cli, ["analyze-all", "--force"])
    assert mock_analyze.called
    assert "Analyzed 1 call(s)." in result.output


def test_build_report_command_writes_file(settings_env, tmp_path):
    out_path = tmp_path / "reports" / "BUG_REPORT.md"
    runner = CliRunner()
    result = runner.invoke(cli, ["build-report", "--out", str(out_path)])
    assert result.exit_code == 0
    assert out_path.exists()
