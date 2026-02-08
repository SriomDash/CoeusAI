from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

import yaml
from jinja2 import Template


@dataclass(frozen=True)
class PromptBundle:
    system_prompt: str
    injection_patterns: tuple[str, ...]
    handling: Dict[str, Any]


def _repo_relative_path() -> Path:
    return Path(__file__).resolve().parent / "system_guardrails.yaml.j2"


@lru_cache(maxsize=1)
def load_guardrails_context(**jinja_vars: Any) -> PromptBundle:
    """
    Loads YAML+Jinja2 template once per process, renders it with jinja_vars,
    and returns a typed bundle.
    """
    path = _repo_relative_path()
    raw = path.read_text(encoding="utf-8")

    rendered = Template(raw).render(**jinja_vars)
    data: Dict[str, Any] = yaml.safe_load(rendered) or {}

    # System prompt
    system_template = (
        (((data.get("prompts") or {}).get("system") or {}).get("template"))
        or ""
    ).strip()

    # Injection patterns
    patterns: List[str] = (
        (((data.get("guardrails") or {}).get("injection_patterns") or {}).get("patterns"))
        or []
    )

    # Handling
    handling: Dict[str, Any] = (
        (((data.get("guardrails") or {}).get("handling")) or {})
    )

    return PromptBundle(
        system_prompt=system_template,
        injection_patterns=tuple(p.strip() for p in patterns if isinstance(p, str) and p.strip()),
        handling=handling,
    )

class _PromptsAccessor:
    def guardrails(self, **jinja_vars: Any) -> PromptBundle:
        return load_guardrails_context(**jinja_vars)


s = _PromptsAccessor()