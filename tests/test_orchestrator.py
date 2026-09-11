import json
from unittest.mock import MagicMock, patch

import bot.orchestrator as orchestrator_module
from bot.orchestrator import CallResult, results_summary, run_batch, run_call
from bot.personas import get_scenario


def _fake_call(sid="CA123", status="completed", duration="42"):
    return MagicMock(sid=sid, status=status, duration=duration)


def test_run_call_success_writes_metadata_and_returns_result(settings_env, tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "CALLS_DIR", tmp_path)
    from bot.config import get_settings

    settings = get_settings()
    scenario = get_scenario("simple_scheduling_new_patient")

    with (
        patch.object(orchestrator_module, "build_client", return_value=MagicMock()),
        patch.object(orchestrator_module, "place_call", return_value=_fake_call()) as mock_place,
        patch.object(orchestrator_module, "wait_for_call_completion", return_value=_fake_call()),
        patch.object(orchestrator_module, "fetch_recording", return_value=None),
    ):
        result = run_call(scenario, settings=settings)

    assert mock_place.called
    assert isinstance(result, CallResult)
    assert result.ok
    assert result.status == "completed"
    assert result.duration_seconds == 42

    metadata_path = tmp_path / result.call_id / "metadata.json"
    assert metadata_path.exists()
    metadata = json.loads(metadata_path.read_text())
    assert metadata["scenario_id"] == "simple_scheduling_new_patient"
    assert metadata["call_sid"] == "CA123"


def test_run_call_handles_telephony_error_gracefully(settings_env, tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "CALLS_DIR", tmp_path)
    from bot.config import get_settings

    settings = get_settings()
    scenario = get_scenario("simple_scheduling_new_patient")

    with (
        patch.object(orchestrator_module, "build_client", return_value=MagicMock()),
        patch.object(orchestrator_module, "place_call", side_effect=RuntimeError("twilio down")),
    ):
        result = run_call(scenario, settings=settings)

    assert not result.ok
    assert result.status == "error"
    assert "twilio down" in result.error


def test_run_batch_runs_every_scenario_and_paces_between_calls(settings_env, tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "CALLS_DIR", tmp_path)
    from bot.config import get_settings
    from bot.personas import load_all_scenarios

    settings = get_settings()
    scenarios = load_all_scenarios()[:3]

    fake_result = CallResult(
        call_id="c",
        scenario_id="s",
        call_sid="CA1",
        status="completed",
        duration_seconds=10,
        recording_path=None,
        transcript_path=None,
    )

    with (
        patch.object(orchestrator_module, "run_call", return_value=fake_result) as mock_run_call,
        patch.object(orchestrator_module.time, "sleep") as mock_sleep,
    ):
        results = run_batch(scenarios, settings=settings, delay_seconds=5)

    assert mock_run_call.call_count == 3
    # paced between calls but not after the last one
    assert mock_sleep.call_count == 2
    mock_sleep.assert_called_with(5)
    assert len(results) == 3


def test_run_batch_skips_delay_when_zero(settings_env, tmp_path, monkeypatch):
    monkeypatch.setattr(orchestrator_module, "CALLS_DIR", tmp_path)
    from bot.config import get_settings
    from bot.personas import load_all_scenarios

    settings = get_settings()
    scenarios = load_all_scenarios()[:2]
    fake_result = CallResult(
        call_id="c", scenario_id="s", call_sid="CA1", status="completed",
        duration_seconds=1, recording_path=None, transcript_path=None,
    )

    with (
        patch.object(orchestrator_module, "run_call", return_value=fake_result),
        patch.object(orchestrator_module.time, "sleep") as mock_sleep,
    ):
        run_batch(scenarios, settings=settings, delay_seconds=0)

    mock_sleep.assert_not_called()


def test_results_summary_reports_ok_and_fail_counts():
    ok = CallResult(
        call_id="c1", scenario_id="s1", call_sid="CA1", status="completed",
        duration_seconds=10, recording_path=None, transcript_path=None,
    )
    failed = CallResult(
        call_id="c2", scenario_id="s2", call_sid=None, status="error",
        duration_seconds=None, recording_path=None, transcript_path=None, error="boom",
    )

    summary = results_summary([ok, failed])
    assert "1/2 calls completed successfully" in summary
    assert "OK" in summary
    assert "FAIL" in summary
    assert "boom" in summary
