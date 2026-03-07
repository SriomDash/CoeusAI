import re
from typing import List, Dict, Any

from backend.clients.gemini_client import gemini_bus
from backend.utils.prompt_loader import load_prompt


class AnswerService:
    @staticmethod
    def _clean_text(text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"https?://\S+", "", text)
        text = text.replace("\u200b", " ")
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        return text.strip()

    @staticmethod
    def _extract_content_only(text: str) -> str:
        """
        If chunk text contains labels like:
        Summary:
        Keywords:
        Search Terms:
        Content:
        then keep only the actual content part.
        """
        if not text:
            return ""

        match = re.search(r"Content:\s*(.*)$", text, flags=re.DOTALL | re.IGNORECASE)
        if match:
            text = match.group(1)

        return AnswerService._clean_text(text)

    @staticmethod
    def _format_chunks_for_prompt(chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return "No evidence available."

        evidence_blocks = []

        for idx, item in enumerate(chunks, start=1):
            raw_content = item.get("content", "") or ""
            content = AnswerService._extract_content_only(raw_content)

            if not content:
                continue

            evidence_blocks.append(f"Evidence {idx}:\n{content}")

        return "\n\n".join(evidence_blocks) if evidence_blocks else "No evidence available."

    @staticmethod
    async def generate_answer(
        query: str,
        reranked_chunks: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        if not query or not query.strip():
            return {
                "answer": "No question was provided.",
                "used_chunks": [],
                "total_chunks": 0,
            }

        if not reranked_chunks:
            return {
                "answer": "I could not find enough relevant evidence to answer that from the indexed documents.",
                "used_chunks": [],
                "total_chunks": 0,
            }

        selected_chunks = reranked_chunks[:top_k]
        evidence_text = AnswerService._format_chunks_for_prompt(selected_chunks)

        system_msg = load_prompt(
            "backend/prompts/answering_agent/prompt.yaml",
            "system_prompt",
        )
        user_msg = load_prompt(
            "backend/prompts/answering_agent/prompt.yaml",
            "user_prompt_template",
            query=query.strip(),
            evidence_chunks=evidence_text,
        )

        response = await gemini_bus.model.ainvoke([
            ("system", system_msg),
            ("human", user_msg),
        ])

        answer_text = (
            str(response.content).strip()
            if hasattr(response, "content")
            else str(response).strip()
        )

        return {
            "answer": answer_text,
            "used_chunks": [
                {
                    "chunk_id": item.get("chunk_id"),
                    "document_id": item.get("document_id"),
                    "source": item.get("source"),
                    "page": item.get("page"),
                    "chunk_index": item.get("chunk_index"),
                    "rerank_score": item.get("rerank_score", 0.0),
                }
                for item in selected_chunks
            ],
            "total_chunks": len(selected_chunks),
        }