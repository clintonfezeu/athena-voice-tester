from unittest.mock import MagicMock, patch

from bot.telephony import build_client, fetch_recording, place_call, wait_for_call_completion


def test_build_client_uses_settings_credentials(settings_env):
    from bot.config import get_settings

    settings = get_settings()
    client = build_client(settings)
    assert client.account_sid == settings.twilio_account_sid


def test_place_call_dials_target_with_recording_enabled(settings_env):
    from bot.config import get_settings

    settings = get_settings()
    client = MagicMock()
    client.calls.create.return_value = MagicMock(sid="CA123")

    call = place_call(client, settings, scenario_id="simple_scheduling_new_patient", call_id="call-1")

    assert call.sid == "CA123"
    _, kwargs = client.calls.create.call_args
    assert kwargs["to"] == settings.target_number
    assert kwargs["from_"] == settings.twilio_from_number
    assert kwargs["record"] is True
    assert kwargs["recording_channels"] == "dual"
    assert "scenario_id=simple_scheduling_new_patient" in kwargs["url"]
    assert "call_id=call-1" in kwargs["url"]


def test_wait_for_call_completion_polls_until_terminal(settings_env):
    client = MagicMock()
    statuses = iter(["queued", "ringing", "in-progress", "completed"])
    client.calls.return_value.fetch.side_effect = lambda: MagicMock(status=next(statuses))

    with patch("bot.telephony.time.sleep"):
        call = wait_for_call_completion(client, "CA123", max_wait_seconds=30, poll_interval=0)

    assert call.status == "completed"


def test_wait_for_call_completion_gives_up_after_max_wait(settings_env):
    client = MagicMock()
    client.calls.return_value.fetch.return_value = MagicMock(status="in-progress")

    times = iter([0, 0, 100])  # third monotonic() call exceeds a 10s deadline
    with patch("bot.telephony.time.monotonic", side_effect=lambda: next(times)):
        with patch("bot.telephony.time.sleep"):
            call = wait_for_call_completion(client, "CA123", max_wait_seconds=10, poll_interval=0)

    assert call.status == "in-progress"


def test_fetch_recording_returns_none_when_no_recording_exists(settings_env, tmp_path):
    from bot.config import get_settings

    settings = get_settings()
    client = MagicMock()
    client.calls.return_value.recordings.list.return_value = []

    result = fetch_recording(client, settings, "CA123", tmp_path)
    assert result is None


def test_fetch_recording_downloads_mp3(settings_env, tmp_path):
    from bot.config import get_settings

    settings = get_settings()
    client = MagicMock()
    recording = MagicMock(uri="/2010-04-01/Accounts/ACtest/Recordings/RE123.json")
    client.calls.return_value.recordings.list.return_value = [recording]

    fake_response = MagicMock(content=b"fake-mp3-bytes")
    fake_response.raise_for_status.return_value = None

    with patch("bot.telephony.httpx.Client") as mock_http_client:
        mock_http_client.return_value.__enter__.return_value.get.return_value = fake_response
        result = fetch_recording(client, settings, "CA123", tmp_path)

    assert result == tmp_path / "recording.mp3"
    assert result.read_bytes() == b"fake-mp3-bytes"
