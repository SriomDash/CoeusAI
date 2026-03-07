from typing import Optional, List, Dict, Any

from backend.config import settings
from backend.clients.elastic_search_client import elastic_bus


class KeywordRetriever:
    def __init__(self) -> None:
        self.index_name = settings.ELASTIC_SEARCH_INDEX

    @staticmethod
    def _normalize_terms(values: Optional[List[str]]) -> List[str]:
        seen = set()
        cleaned = []

        for value in values or []:
            v = str(value).strip()
            if not v:
                continue
            key = v.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned.append(v)

        return cleaned

    async def search(
        self,
        query: str,
        user_id: str,
        document_id: Optional[str] = None,
        source: Optional[str] = None,
        top_k: int = 10,
        expanded_keywords: Optional[List[str]] = None,
        expanded_search_terms: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        if not query or not query.strip():
            return []

        client = elastic_bus.get_client()

        filters = [{"term": {"user_id": user_id}}]

        if document_id:
            filters.append({"term": {"document_id": document_id}})

        if source:
            filters.append({"term": {"source": source.lower()}})

        expanded_keywords = self._normalize_terms(expanded_keywords)
        expanded_search_terms = self._normalize_terms(expanded_search_terms)

        combined_parts = [query.strip()]
        combined_parts.extend(expanded_keywords)
        combined_parts.extend(expanded_search_terms)
        combined_query = " | ".join(combined_parts)

        body = {
            "size": top_k,
            "query": {
                "bool": {
                    "filter": filters,
                    "should": [
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "content^4",
                                    "summary^3",
                                    "keywords^2",
                                    "search_terms^2"
                                ],
                                "type": "best_fields",
                                "operator": "or"
                            }
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "content^5",
                                    "summary^4"
                                ],
                                "type": "phrase",
                                "boost": 4
                            }
                        },
                        {
                            "multi_match": {
                                "query": query,
                                "fields": [
                                    "content^3",
                                    "summary^3",
                                    "keywords^3",
                                    "search_terms^3"
                                ],
                                "type": "phrase_prefix",
                                "boost": 2
                            }
                        },
                        {
                            "simple_query_string": {
                                "query": combined_query,
                                "fields": [
                                    "content^3",
                                    "summary^4",
                                    "keywords^4",
                                    "search_terms^4"
                                ],
                                "default_operator": "or",
                                "boost": 2
                            }
                        }
                    ],
                    "minimum_should_match": 1
                }
            },
            "sort": [
                {"_score": {"order": "desc"}}
            ]
        }

        print("KeywordRetriever query body:", body)

        response = await client.search(index=self.index_name, body=body)
        hits = response.get("hits", {}).get("hits", [])

        print("KeywordRetriever top hits:", [
            {
                "id": hit.get("_source", {}).get("id"),
                "score": hit.get("_score")
            }
            for hit in hits[:5]
        ])

        return [self._normalize_hit(hit) for hit in hits]

    @staticmethod
    def _normalize_hit(hit: Dict[str, Any]) -> Dict[str, Any]:
        source = hit.get("_source", {})

        return {
            "chunk_id": source.get("id"),
            "document_id": source.get("document_id"),
            "source": source.get("source"),
            "page": source.get("page"),
            "chunk_index": source.get("chunk_index"),
            "content": source.get("content", ""),
            "summary": source.get("summary"),
            "keywords": source.get("keywords"),
            "search_terms": source.get("search_terms"),
            "score": float(hit.get("_score", 0.0)),
            "retrieval_type": "keyword",
        }