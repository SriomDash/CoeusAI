from __future__ import annotations

import random
import time
from typing import Iterator, Optional

from openai import APIError, APITimeoutError, RateLimitError

from backend.clients.llm_client import get_llm_client
from backend.config.settings import get_settings
from backend.prompts import s as prompts


def _guardrails():
    return prompts.guardrails()


def sanitize_user_input(text: str) -> str:
    settings = get_settings()
    bundle = _guardrails()

    if text is None:
        raise ValueError("User input cannot be None")

    t = text.strip()
    if not t:
        raise ValueError("User input cannot be empty")

    if len(t) > settings.max_input_chars:
        raise ValueError(f"User input too long (>{settings.max_input_chars} chars).")

    lowered = t.lower()
    if any(p in lowered for p in bundle.injection_patterns):
        handling = bundle.handling or {}
        mode = (handling.get("mode") or "soft").lower()
        prepend_warning = bool(handling.get("prepend_warning", True))
        warning_text = (handling.get("warning_text") or "").strip()

        if mode == "block":
            raise ValueError("Possible prompt-injection detected. Request blocked.")

        if prepend_warning and warning_text:
            return f"{warning_text}\n\n{t}"

    return t


def with_retries(fn, *, max_retries: int) -> object:
    last_exc: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            return fn()
        except (RateLimitError, APITimeoutError, APIError) as exc:
            last_exc = exc
            if attempt >= max_retries:
                break
            base = 0.5 * (2 ** (attempt - 1))  
            jitter = random.uniform(0, 0.25)
            time.sleep(base + jitter)

    raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_exc}") from last_exc


def generate(user_text: str) -> str:
    settings = get_settings()
    client = get_llm_client()
    bundle = _guardrails()

    safe_text = sanitize_user_input(user_text)

    def _call():
        return client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": bundle.system_prompt},
                {"role": "user", "content": safe_text},
            ],
            temperature=0.2,
            max_tokens=512,
        )

    resp = with_retries(_call, max_retries=settings.max_retries)
    return (resp.choices[0].message.content or "").strip()


def stream_generate(user_text: str) -> Iterator[str]:
    settings = get_settings()
    client = get_llm_client()
    bundle = _guardrails()

    safe_text = sanitize_user_input(user_text)

    def _call():
        return client.chat.completions.create(
            model=settings.model,
            messages=[
                {"role": "system", "content": bundle.system_prompt},
                {"role": "user", "content": safe_text},
            ],
            temperature=0.2,
            max_tokens=512,
            stream=True,
        )

    stream = with_retries(_call, max_retries=settings.max_retries)

    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta