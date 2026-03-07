from datetime import datetime, timezone
from typing import List, Dict, Any

from elasticsearch import helpers
# 1. Import traceable from LangSmith
from langsmith import traceable

from backend.config import settings
from backend.clients.elastic_search_client import elastic_bus


class ElasticService:
    @staticmethod
    @traceable(name="Elastic: Ensure Index", run_type="tool") # 2. Trace index verification
    async def ensure_index(index_name: str) -> None:
        """
        Create the Elasticsearch index if it does not already exist.
        The mapping is designed for:
        - exact identifier filtering
        - strong keyword matching
        - phrase search on content/summary/search_terms
        """
        client = elastic_bus.get_client()

        exists = await client.indices.exists(index=index_name)
        if exists:
            return

        print(f"Creating index: {index_name}...")

        mapping = {
            "settings": {
                "analysis": {
                    "normalizer": {
                        "lowercase_normalizer": {
                            "type": "custom",
                            "filter": ["lowercase"]
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "id": {"type": "keyword"},
                    "user_id": {"type": "keyword"},
                    "job_id": {"type": "keyword"},
                    "document_id": {"type": "keyword"},
                    "source": {
                        "type": "keyword",
                        "normalizer": "lowercase_normalizer"
                    },
                    "page": {"type": "integer"},
                    "chunk_index": {"type": "integer"},

                    "content": {
                        "type": "text",
                        "fields": {
                            "raw": {"type": "keyword", "ignore_above": 32766}
                        }
                    },
                    "summary": {
                        "type": "text",
                        "fields": {
                            "raw": {"type": "keyword", "ignore_above": 2048}
                        }
                    },
                    "keywords": {
                        "type": "text",
                        "fields": {
                            "raw": {"type": "keyword", "ignore_above": 2048}
                        }
                    },
                    "search_terms": {
                        "type": "text",
                        "fields": {
                            "raw": {"type": "keyword", "ignore_above": 2048}
                        }
                    },

                    "created_at": {"type": "date"},
                    "updated_at": {"type": "date"}
                }
            }
        }

        await client.indices.create(index=index_name, body=mapping)

    @staticmethod
    def _build_elastic_doc(item: Dict[str, Any], now_iso: str) -> Dict[str, Any]:
        """
        Convert enriched chunk structure into Elasticsearch _source format.
        """
        source_meta = item.get("source_metadata", {})
        ai_meta = item.get("ai_metadata", {})

        return {
            "id": item["id"],
            "user_id": str(item.get("user_id", "")),
            "job_id": str(item.get("job_id", "")),
            "document_id": str(item.get("document_id", "")),
            "source": str(source_meta.get("source", "")),
            "page": int(source_meta.get("page", 0)),
            "chunk_index": int(source_meta.get("chunk_index", 0)),
            "content": item.get("content", ""),
            "summary": item.get("summary", ""),
            "keywords": " ".join(ai_meta.get("keywords", [])),
            "search_terms": " ".join(ai_meta.get("search_terms", [])),
            "created_at": now_iso,
            "updated_at": now_iso,
        }

    @classmethod
    @traceable(name="Elastic: Bulk Insert Chunks", run_type="tool") # 3. Trace the bulk indexing operation
    async def bulk_insert_chunks(
        cls,
        enriched_chunks: List[Dict[str, Any]],
    ) -> int:
        """
        Upsert enriched chunks into Elasticsearch.

        Behavior:
        - same chunk id in Elasticsearch and Chroma
        - same document re-ingestion updates indexed chunks
        - optimized for exact keyword and phrase retrieval
        """
        if not enriched_chunks:
            return 0

        client = elastic_bus.get_client()
        index_name = settings.ELASTIC_SEARCH_INDEX

        try:
            await cls.ensure_index(index_name)

            now_iso = datetime.now(timezone.utc).isoformat()
            actions = []

            for item in enriched_chunks:
                content = item.get("content", "").strip()
                if not content:
                    continue

                action = {
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": item["id"],
                    "_source": cls._build_elastic_doc(item, now_iso),
                }
                actions.append(action)

            if not actions:
                print("No valid chunks to index in Elasticsearch.")
                return 0

            success_count, errors = await helpers.async_bulk(
                client,
                actions,
                refresh=True,
            )

            if errors:
                print(f"Elastic Errors: {errors}")

            print(f"Indexed/updated {success_count} documents in Elasticsearch.")
            return success_count

        except Exception as e:
            print(f"Elastic Service Error: {e}")
            raise e