import instructor
from groq import AsyncGroq
from pydantic import BaseModel, Field
from typing import List, Optional

from backend.config import settings
from backend.utils.prompt_loader import load_prompt


class QueryExpansionResult(BaseModel):
    keywords: List[str] = Field(default_factory=list)
    search_terms: List[str] = Field(default_factory=list)
    intent_summary: str = ""
    topic_hint: Optional[str] = None
    section_hint: Optional[str] = None


class QueryExpansionService:
    @staticmethod
    def _get_instructor_client():
        return instructor.from_groq(
            AsyncGroq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON
        )

    @staticmethod
    def _normalize_terms(values: List[str]) -> List[str]:
        seen = set()
        cleaned = []

        for value in values or []:
            v = str(value).strip()
            if not v:
                continue
            if len(v) < 2:
                continue

            key = v.lower()
            if key in seen:
                continue

            seen.add(key)
            cleaned.append(v)

        return cleaned

    @staticmethod
    async def expand_query(query: str) -> QueryExpansionResult:
        if not query or not query.strip():
            return QueryExpansionResult()

        client = QueryExpansionService._get_instructor_client()

        try:
            system_msg = load_prompt(
                "backend/prompts/query_expansion_agent/prompt.yaml",
                "system_prompt"
            )
            user_msg = load_prompt(
                "backend/prompts/query_expansion_agent/prompt.yaml",
                "user_prompt_template",
                query=query.strip()
            )
        except Exception as e:
            print(f"Query Expansion Prompt Loading Failed: {e}")
            raise

        try:
            result = await client.chat.completions.create(
                model=settings.GROQ_MODEL,
                response_model=QueryExpansionResult,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_retries=2,
            )

            result.keywords = QueryExpansionService._normalize_terms(result.keywords)
            result.search_terms = QueryExpansionService._normalize_terms(result.search_terms)

            if not result.intent_summary:
                result.intent_summary = query.strip()

            return result

        except Exception as e:
            print(f"Query Expansion Failed: {e}")

            # better fallback than empty arrays
            return QueryExpansionResult(
                keywords=[],
                search_terms=[query.strip()],
                intent_summary=query.strip(),
            )