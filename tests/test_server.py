from fastapi.testclient import TestClient


def test_healthz(settings_env):
    from bot.server import app

    client = TestClient(app)
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_twiml_returns_stream_pointing_at_media_stream(settings_env):
    from bot.server import app

    client = TestClient(app)
    resp = client.post("/twiml?scenario_id=simple_scheduling_new_patient&call_id=call-123")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")
    assert "<Stream" in resp.text
    assert "wss://example.ngrok-free.app/media-stream" in resp.text
    assert "scenario_id=simple_scheduling_new_patient" in resp.text
    assert "call_id=call-123" in resp.text


def test_media_stream_closes_for_unknown_scenario(settings_env):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    from bot.server import app

    client = TestClient(app)
    # Server closes immediately with policy-violation (1008) for an unknown
    # scenario, before ever dialing OpenAI.
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/media-stream?scenario_id=does-not-exist"):
            pass
    assert exc_info.value.code == 1008
