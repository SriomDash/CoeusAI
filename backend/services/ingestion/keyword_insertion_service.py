from datetime import datetime, timezone
from typing import List, Dict, Any

from elasticsearch import helpers
from langsmith import traceable

# UPDATED: Using our Bus Singletons
from backend.clients.elastic_search_client import elastic_bus
from backend.clients.supabase_client import supabase_bus
from backend.config import settings

class ElasticServiceError(Exception): pass
class InvalidJobStateError(ElasticServiceError): pass
class JobNotFoundError(ElasticServiceError): pass

class ElasticService:
    @staticmethod
    async def _get_job(user_id: str, job_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()

        job_result = (
            await supabase.table("ingestion_jobs")
            .select("id, user_id, document_id, status")
            .eq("id", job_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not job_result.data:
            raise JobNotFoundError(f"Job {job_id} not found.")

        return job_result.data[0]

    @staticmethod
    @traceable(name="Elastic: Ensure Index", run_type="tool")
    async def ensure_index(index_name: str) -> None:
        """
        Ensures the Elasticsearch index exists with correct mappings for RAG.
        """
        # Already using the bus client, which is perfect
        client = elastic_bus.get_client()

        exists = await client.indices.exists(index=index_name)
        if exists:
            return

        # ... mapping definition remains identical ...
        await client.indices.create(index=index_name, body=mapping)

    @classmethod
    @traceable(name="Elastic: Bulk Insert Chunks", run_type="chain")
    async def bulk_insert_chunks(
        cls,
        enriched_chunks: List[Dict[str, Any]],
        user_id: str,
        job_id: str,
    ) -> int:
        """
        Performs bulk indexing of text chunks into Elasticsearch.
        """
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()
        job = await cls._get_job(user_id=user_id, job_id=job_id)

        # 1. State Guard: Only run if vectors are already safe in Chroma
        if job["status"] != "vectors_inserted":
            raise InvalidJobStateError(f"Cannot index keywords for job status: {job['status']}")

        client = elastic_bus.get_client()
        index_name = settings.ELASTIC_SEARCH_INDEX

        try:
            await cls.ensure_index(index_name)
            now_iso = datetime.now(timezone.utc).isoformat()
            
            # 2. Build the bulk actions list
            actions = []
            for item in enriched_chunks:
                # Validation checks...
                actions.append({
                    "_op_type": "index",
                    "_index": index_name,
                    "_id": item["id"],
                    "_source": cls._build_elastic_doc(item, now_iso),
                })

            # 3. Perform Bulk Operation
            success_count, errors = await helpers.async_bulk(
                client,
                actions,
                refresh=True,
            )

            # 4. Finalize State
            await supabase.table("ingestion_jobs").update(
                {"status": "keyword_inserted"}
            ).eq("id", job_id).execute()

            return success_count

        except Exception as e:
            await supabase.table("ingestion_jobs").update({
                "status": "failed",
                "error_message": str(e),
            }).eq("id", job_id).execute()
            raise e