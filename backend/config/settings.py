from __future__ import annotations

import os
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    api_key: str = Field(..., alias="GROQ_API_KEY")
    base_url: str = Field("https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    model: str = Field(..., alias="GROQ_MODEL")

    request_timeout_s: float = Field(30.0, alias="REQUEST_TIMEOUT_S")
    max_retries: int = Field(3, alias="MAX_RETRIES")
    max_input_chars: int = Field(4000, alias="MAX_INPUT_CHARS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()