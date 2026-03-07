from typing import List, Dict, Any


class FusionService:
    """
    Hybrid retrieval fusion service using Reciprocal Rank Fusion (RRF).

    Why RRF:
    - semantic and keyword scores are on different scales
    - rank positions are more stable than raw score comparison
    - simple and robust baseline for hybrid retrieval
    """

    @staticmethod
    def reciprocal_rank_fusion(
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        rrf_k: int = 60,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Fuse semantic + keyword retrieval results using chunk_id as the shared identity.

        Args:
            semantic_results: normalized semantic retrieval results
            keyword_results: normalized keyword retrieval results
            rrf_k: standard RRF constant, commonly 60
            top_k: number of fused results to return

        Returns:
            List of fused normalized retrieval results sorted by fused_score desc
        """
        fused_scores: Dict[str, float] = {}
        fused_items: Dict[str, Dict[str, Any]] = {}
        source_presence: Dict[str, Dict[str, bool]] = {}

        FusionService._accumulate_rrf(
            results=semantic_results,
            fused_scores=fused_scores,
            fused_items=fused_items,
            source_presence=source_presence,
            source_name="semantic",
            rrf_k=rrf_k,
        )

        FusionService._accumulate_rrf(
            results=keyword_results,
            fused_scores=fused_scores,
            fused_items=fused_items,
            source_presence=source_presence,
            source_name="keyword",
            rrf_k=rrf_k,
        )

        fused_results: List[Dict[str, Any]] = []

        for chunk_id, item in fused_items.items():
            result = dict(item)

            result["fused_score"] = float(round(fused_scores.get(chunk_id, 0.0), 8))
            result["semantic_match"] = source_presence.get(chunk_id, {}).get("semantic", False)
            result["keyword_match"] = source_presence.get(chunk_id, {}).get("keyword", False)
            result["retrieval_type"] = FusionService._build_retrieval_label(
                semantic_match=result["semantic_match"],
                keyword_match=result["keyword_match"],
            )

            fused_results.append(result)

        fused_results.sort(
            key=lambda x: (
                x.get("fused_score", 0.0),
                1 if x.get("semantic_match") else 0,
                1 if x.get("keyword_match") else 0,
            ),
            reverse=True,
        )

        print("Fusion top results:", [
            {
                "chunk_id": item.get("chunk_id"),
                "fused_score": item.get("fused_score"),
                "semantic_match": item.get("semantic_match"),
                "keyword_match": item.get("keyword_match"),
            }
            for item in fused_results[:top_k]
        ])

        return fused_results[:top_k]

    @staticmethod
    def _accumulate_rrf(
        results: List[Dict[str, Any]],
        fused_scores: Dict[str, float],
        fused_items: Dict[str, Dict[str, Any]],
        source_presence: Dict[str, Dict[str, bool]],
        source_name: str,
        rrf_k: int,
    ) -> None:
        """
        Add RRF contribution from one ranked result list.
        """
        for rank, item in enumerate(results, start=1):
            chunk_id = item.get("chunk_id")
            if not chunk_id:
                continue

            rrf_score = 1.0 / (rrf_k + rank)
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + rrf_score

            if chunk_id not in fused_items:
                fused_items[chunk_id] = FusionService._build_base_fused_item(item)
            else:
                fused_items[chunk_id] = FusionService._merge_items(
                    existing=fused_items[chunk_id],
                    incoming=item,
                )

            if chunk_id not in source_presence:
                source_presence[chunk_id] = {
                    "semantic": False,
                    "keyword": False,
                }

            source_presence[chunk_id][source_name] = True

            if source_name == "semantic":
                fused_items[chunk_id]["semantic_score"] = item.get("score", 0.0)
                fused_items[chunk_id]["semantic_distance"] = item.get("distance")
            elif source_name == "keyword":
                fused_items[chunk_id]["keyword_score"] = item.get("score", 0.0)

    @staticmethod
    def _build_base_fused_item(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build the base normalized fused item from the first occurrence of a chunk.
        """
        return {
            "chunk_id": item.get("chunk_id"),
            "document_id": item.get("document_id"),
            "source": item.get("source"),
            "page": item.get("page"),
            "chunk_index": item.get("chunk_index"),
            "content": item.get("content", ""),
            "summary": item.get("summary"),
            "keywords": item.get("keywords", []),
            "search_terms": item.get("search_terms", []),
            "semantic_score": None,
            "semantic_distance": None,
            "keyword_score": None,
        }

    @staticmethod
    def _merge_items(existing: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge fields when the same chunk appears in multiple retrieval lists.
        Prefer non-empty richer fields.
        """
        merged = dict(existing)

        for field in [
            "document_id",
            "source",
            "page",
            "chunk_index",
            "content",
            "summary",
            "keywords",
            "search_terms",
        ]:
            existing_value = merged.get(field)
            incoming_value = incoming.get(field)

            if FusionService._is_better_value(existing_value, incoming_value):
                merged[field] = incoming_value

        return merged

    @staticmethod
    def _is_better_value(existing: Any, incoming: Any) -> bool:
        """
        Decide whether incoming field is better than existing one.
        """
        if existing in (None, "", [], {}):
            return incoming not in (None, "", [], {})
        return False

    @staticmethod
    def _build_retrieval_label(semantic_match: bool, keyword_match: bool) -> str:
        """
        Label fused result origin.
        """
        if semantic_match and keyword_match:
            return "hybrid"
        if semantic_match:
            return "semantic"
        if keyword_match:
            return "keyword"
        return "unknown"
    