"""Application-wide settings loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # OpenClaw / kiloclaw
    openclaw_api_key: str = ""
    openclaw_base_url: str = "https://api.kiloclaw.io"

    # boxd
    boxd_endpoint: str = "http://localhost:2375"
    boxd_vm_image: str = "claude-code:latest"

    # Context persistence
    context_store_path: Path = Path("~/.dev-threads/contexts")

    # Voice
    voice_wake_word: str = "hey threads"
    voice_language: str = "en-US"

    # Logging
    log_level: str = "INFO"

    def expanded_context_store_path(self) -> Path:
        return self.context_store_path.expanduser()


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
