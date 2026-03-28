"""Minimal settings for dev-threads."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    boxd_endpoint: str = "http://localhost:2375"
    boxd_vm_image: str = "ghcr.io/anthropics/claude-code:latest"
    task_timeout: float = 300.0


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
