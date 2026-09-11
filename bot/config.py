"""Application configuration, loaded from environment variables / .env."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Twilio ---------------------------------------------------------
    twilio_account_sid: str = Field(..., alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str = Field(..., alias="TWILIO_AUTH_TOKEN")
    twilio_from_number: str = Field(..., alias="TWILIO_FROM_NUMBER")

    # --- OpenAI -----------------------------------------------------------
    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_realtime_model: str = Field("gpt-realtime", alias="OPENAI_REALTIME_MODEL")
    openai_analysis_model: str = Field("gpt-5.1", alias="OPENAI_ANALYSIS_MODEL")

    # --- Target under test ------------------------------------------------
    target_number: str = Field("+18054398008", alias="TARGET_NUMBER")

    # --- Server / public webhook -------------------------------------------
    public_base_url: str = Field(..., alias="PUBLIC_BASE_URL")
    host: str = Field("0.0.0.0", alias="HOST")
    port: int = Field(8000, alias="PORT")

    # --- Call pacing / safety -----------------------------------------------
    batch_call_delay_seconds: int = Field(30, alias="BATCH_CALL_DELAY_SECONDS")
    max_call_duration_seconds: int = Field(240, alias="MAX_CALL_DURATION_SECONDS")

    @field_validator("public_base_url")
    @classmethod
    def _strip_trailing_slash(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def public_host(self) -> str:
        """Bare host[:port] with any scheme stripped."""
        return self.public_base_url.split("://", 1)[-1]

    @property
    def websocket_url(self) -> str:
        """wss:// URL Twilio's <Stream> should connect to."""
        return f"wss://{self.public_host}/media-stream"

    @property
    def twiml_url(self) -> str:
        """Public https:// URL Twilio should fetch TwiML from."""
        return f"{self.public_base_url}/twiml"


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton. Raises a clear pydantic error if `.env` is incomplete."""
    return Settings()
