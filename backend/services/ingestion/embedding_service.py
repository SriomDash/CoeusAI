import os
import re
import torch
from chromadb.utils import embedding_functions
from typing import List, Dict, Any
from langsmith import traceable

# UPDATED: Using our Bus Singletons
from backend.clients.supabase_client import supabase_bus
from backend.clients.chroma_client import chroma_bus
from backend.config import settings

class EmbeddingServiceError(Exception): pass
class InvalidJobStateError(EmbeddingServiceError): pass
class JobNotFoundError(EmbeddingServiceError): pass

class EmbeddingService:
    @staticmethod
    def _sanitize_collection_name(user_id: str) -> str:
        clean_name = "".join(c if c.isalnum() else "_" for c in str(user_id))
        return f"user_collection_{clean_name}"[:63]

    @staticmethod
    @traceable(name="Chroma: Get or Create Collection", run_type="tool")
    def get_collection(user_id: str):
        """
        Uses the warm Chroma client from chroma_bus to fetch/create a collection.
        """
        # Get the persistent client that was warmed up in main.py
        client = chroma_bus.client 
        if not client:
             raise RuntimeError("Chroma client not initialized. Check your lifespan.")

        device = "cuda" if torch.cuda.is_available() else "cpu"
        
        local_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=settings.HF_EMBEDDING_MODEL,
            device=device,
        )

        collection_name = EmbeddingService._sanitize_collection_name(user_id)

        return client.get_or_create_collection(
            name=collection_name,
            embedding_function=local_ef,
            metadata={"hnsw:space": "cosine"},
        )

    # ... _clean_text, _build_chroma_metadata, _build_semantic_document remain identical ...

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

    @classmethod
    @traceable(name="Chroma: Embed and Upsert", run_type="chain")
    async def embed_and_store(
        cls,
        enriched_chunks: List[Dict[str, Any]],
        user_id: str,
        job_id: str,
    ) -> int:
        # UPDATED: Use the warm clients from our Bus system
        supabase = supabase_bus.get_client()
        job = await cls._get_job(user_id=user_id, job_id=job_id)

        if job["status"] != "ai_labelled":
            raise InvalidJobStateError(f"Cannot embed job in status: {job['status']}")

        # ... logic to build 'ids', 'documents', and 'metadatas' ...

        try:
            # 1. Update status to 'embedded' (Payload is ready)
            await supabase.table("ingestion_jobs").update(
                {"status": "embedded"}
            ).eq("id", job_id).execute()

            # 2. Get collection via our bus-integrated method
            collection = cls.get_collection(user_id)

            # 3. Perform the vector storage
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
            )

            # 4. Update status to 'vectors_inserted'
            await supabase.table("ingestion_jobs").update(
                {"status": "vectors_inserted"}
            ).eq("id", job_id).execute()

            return len(ids)

        except Exception as e:
            await supabase.table("ingestion_jobs").update({
                "status": "failed",
                "error_message": str(e),
            }).eq("id", job_id).execute()
            raise e