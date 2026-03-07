import re
from typing import List, Dict, Any

from backend.config import settings
from backend.clients.cohere_client import co_bus


class RerankerService:
    """
    Reranks fused retrieval candidates using Cohere.

    Intended flow:
    query
    -> keyword + semantic retrieval
    -> fusion
    -> rerank fused candidates
    -> send top reranked chunks to Gemini
    """

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
    def _build_rerank_documents(
        candidates: List[Dict[str, Any]],
        use_summary: bool = True,
    ) -> List[str]:
        """
        Build rerankable text documents from retrieved chunks.

        Best practice:
        - rerank on cleaned chunk content
        - optionally prepend summary
        - include light structural cues like page/source
        """
        documents: List[str] = []

        for item in candidates:
            content = RerankerService._clean_text((item.get("content") or "").strip())
            summary = RerankerService._clean_text((item.get("summary") or "").strip())
            source = item.get("source") or ""
            page = item.get("page")

            parts = []

            if source:
                parts.append(f"Source: {source}")
            if page is not None:
                parts.append(f"Page: {page}")
            if use_summary and summary:
                parts.append(f"Summary: {summary}")
            if content:
                parts.append(f"Content: {content}")

            documents.append("\n".join(parts).strip())

        return documents

    @staticmethod
    def rerank(
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: int = 5,
        use_summary: bool = True,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        if not candidates:
            return []

        documents = RerankerService._build_rerank_documents(
            candidates=candidates,
            use_summary=use_summary,
        )

        print("Reranker input chunk_ids:", [c.get("chunk_id") for c in candidates[:10]])

        try:
            response = co_bus.client.rerank(
                model=settings.COHERE_RERANK_MODEL,
                query=query.strip(),
                documents=documents,
                top_n=min(top_k, len(documents)),
            )

            reranked_results: List[Dict[str, Any]] = []

            for item in response.results:
                original_idx = item.index
                original_candidate = candidates[original_idx]

                reranked_item = dict(original_candidate)
                reranked_item["rerank_score"] = float(item.relevance_score)

                reranked_results.append(reranked_item)

            reranked_results.sort(
                key=lambda x: x.get("rerank_score", 0.0),
                reverse=True
            )

            print("Reranker top results:", [
                {
                    "chunk_id": r.get("chunk_id"),
                    "rerank_score": r.get("rerank_score")
                }
                for r in reranked_results
            ])

            return reranked_results

        except Exception as e:
            print(f"Reranking Failed: {e}")

            fallback = []
            for item in candidates[:top_k]:
                copy_item = dict(item)
                copy_item["rerank_score"] = 0.0
                fallback.append(copy_item)

            return fallback