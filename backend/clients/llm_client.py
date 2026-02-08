from __future__ import annotations

from functools import lru_cache
from openai import OpenAI

from backend.config.settings import get_settings

@lru_cache(maxsize=1)
def get_llm_client() -> OpenAI:
    s = get_settings()
    return OpenAI(
        api_key=s.api_key,
        base_url=s.base_url,
        timeout=s.request_timeout_s,
    )