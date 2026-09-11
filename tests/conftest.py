import pytest

REQUIRED_ENV = {
    "TWILIO_ACCOUNT_SID": "ACtest",
    "TWILIO_AUTH_TOKEN": "token",
    "TWILIO_FROM_NUMBER": "+15550001111",
    "OPENAI_API_KEY": "sk-test",
    "PUBLIC_BASE_URL": "https://example.ngrok-free.app",
}


@pytest.fixture
def settings_env(monkeypatch):
    """Set the minimum env vars needed for bot.config.Settings to load."""
    for k, v in REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)
    from bot.config import get_settings

    get_settings.cache_clear()
    yield REQUIRED_ENV
    get_settings.cache_clear()
