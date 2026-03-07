from typing import Optional, List, Dict, Any

from backend.services.embedding_service import EmbeddingService


class SemanticRetriever:
    """
    Chroma semantic retriever.

    Temporary simplified behavior:
    - collection is already scoped per user_id
    - no metadata filtering for now
    - original user query only for embeddings
    """

    async def search(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        source: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        collection = EmbeddingService.get_collection(user_id)

        try:
            response = collection.query(
                query_texts=[query.strip()],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            results = self._normalize_response(response)

            print("Semantic returned chunk ids:", [r["chunk_id"] for r in results[:10]])
            print("Semantic distances:", [r.get("distance") for r in results[:10]])
            print("Semantic pages:", [r.get("page") for r in results[:10]])

            return results

        except Exception as e:
            print(f"Semantic Retriever Error: {e}")
            raise

    @staticmethod
    def _normalize_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
        ids = response.get("ids", [[]])
        documents = response.get("documents", [[]])
        metadatas = response.get("metadatas", [[]])
        distances = response.get("distances", [[]])

        if not ids or not ids[0]:
            return []

        result_ids = ids[0]
        result_docs = documents[0] if documents else []
        result_metas = metadatas[0] if metadatas else []
        result_distances = distances[0] if distances else []

        results: List[Dict[str, Any]] = []

        for idx, chunk_id in enumerate(result_ids):
            metadata = result_metas[idx] if idx < len(result_metas) else {}
            content = result_docs[idx] if idx < len(result_docs) else ""
            distance = result_distances[idx] if idx < len(result_distances) else None

            results.append({
                "chunk_id": chunk_id,
                "document_id": metadata.get("document_id"),
                "source": metadata.get("source"),
                "source_name": metadata.get("source_name"),
                "page": metadata.get("page"),
                "chunk_index": metadata.get("chunk_index"),
                "content": content,
                "summary": metadata.get("summary"),
                "keywords": SemanticRetriever._split_csv_field(metadata.get("keywords")),
                "search_terms": SemanticRetriever._split_csv_field(metadata.get("search_terms")),
                "score": SemanticRetriever._distance_to_score(distance),
                "distance": distance,
                "retrieval_type": "semantic",
            })

        return results

    @staticmethod
    def _split_csv_field(value: Optional[str]) -> List[str]:
        if not value:
            return []
        return [item.strip() for item in str(value).split(",") if item.strip()]

    @staticmethod
    def _distance_to_score(distance: Optional[float]) -> float:
        if distance is None:
            return 0.0
        try:
            return float(1.0 / (1.0 + float(distance)))
        except Exception:
            return 0.0