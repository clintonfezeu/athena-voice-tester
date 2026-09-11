import pytest

REQUIRED_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest",
    "TWILIO_AUTH_TOKEN": "token",
    "TWILIO_FROM_NUMBER": "+15550001111",
    "OPENAI_API_KEY": "sk-test",
    "PUBLIC_BASE_URL": "https://example.ngrok-free.app",
}


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    from bot.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _set_env(monkeypatch, overrides: dict | None = None) -> None:
    env = dict(REQUIRED_ENV)
    env.update(overrides or {})
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_settings_load_from_env(monkeypatch):
    from bot.config import Settings

    _set_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.twilio_account_sid == "ACtest"
    assert settings.target_number == "+18054398008"  # default


def test_settings_missing_required_field_raises(monkeypatch):
    from pydantic import ValidationError

    from bot.config import Settings

    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_public_base_url_trailing_slash_is_stripped(monkeypatch):
    from bot.config import Settings

    _set_env(monkeypatch, {"PUBLIC_BASE_URL": "https://example.ngrok-free.app/"})
    settings = Settings(_env_file=None)
    assert settings.public_base_url == "https://example.ngrok-free.app"


def test_websocket_and_twiml_urls(monkeypatch):
    from bot.config import Settings

    _set_env(monkeypatch)
    settings = Settings(_env_file=None)
    assert settings.websocket_url == "wss://example.ngrok-free.app/media-stream"
    assert settings.twiml_url == "https://example.ngrok-free.app/twiml"


def test_get_settings_is_cached(monkeypatch):
    from bot.config import get_settings

    _set_env(monkeypatch)
    a = get_settings()
    b = get_settings()
    assert a is b
