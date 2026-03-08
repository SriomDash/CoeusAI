import asyncio
from typing import List, Dict, Any

from langsmith import traceable

from backend.clients.groq_client import groq_clients
# UPDATED: Using our Bus Singleton
from backend.clients.supabase_client import supabase_bus
from backend.config import settings
from backend.schemas.chunkings_model import ChunkMetadata, BatchMetadata
from backend.utils.prompt_loader import load_prompt


class LabelingServiceError(Exception): pass
class InvalidJobStateError(LabelingServiceError): pass
class JobNotFoundError(LabelingServiceError): pass


class LabelingService:
    @staticmethod
    @traceable(name="Labeling: LLM Batch Processing", run_type="llm")
    async def label_batch(chunks: List[str]) -> List[ChunkMetadata]:
        """
        Processes one batch of chunk texts and returns structured metadata.
        """
        client = groq_clients.instructor_async_client

        try:
            system_msg = load_prompt(
                "backend/prompts/data_labeling_agent/prompt.yaml",
                "system_prompt"
            )
            user_msg = load_prompt(
                "backend/prompts/data_labeling_agent/prompt.yaml",
                "user_prompt_template",
                chunks=chunks
            )
        except Exception as e:
            print(f"Prompt Loading Failed: {e}")
            raise

        try:
            batch_result = await client.chat.completions.create(
                model=settings.GROQ_MODEL,
                response_model=BatchMetadata,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_retries=2,
            )

            metadata_list = batch_result.metadata_list

            # Handle edge cases where LLM might return fewer items than sent
            if len(metadata_list) != len(chunks):
                while len(metadata_list) < len(chunks):
                    metadata_list.append(
                        ChunkMetadata(
                            keywords=[],
                            search_terms=[],
                            one_line_summary="Error: Missing generation"
                        )
                    )
                metadata_list = metadata_list[:len(chunks)]

            return metadata_list

        except Exception as e:
            print(f"Batch Processing Failed: {e}")
            return [
                ChunkMetadata(keywords=[], search_terms=[], one_line_summary="Processing Error")
                for _ in chunks
            ]

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
    @traceable(name="Labeling: Process and Link", run_type="chain")
    async def process_and_link(
        cls,
        chunk_records: List[Dict[str, Any]],
        user_id: str,
        job_id: str,
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        # UPDATED: Use the bus singleton
        supabase = supabase_bus.get_client()
        job = await cls._get_job(user_id=user_id, job_id=job_id)

        if job["status"] != "chunked":
            raise InvalidJobStateError(f"Job {job_id} is in status '{job['status']}'. Expected 'chunked'.")

        # ... (Scope validation logic remains identical) ...

        try:
            all_chunks = [chunk["content"] for chunk in chunk_records]
            batches = [
                all_chunks[i:i + batch_size]
                for i in range(0, len(all_chunks), batch_size)
            ]

            # CONCURRENCY POWER: Run all batches at the same time
            tasks = [cls.label_batch(batch) for batch in batches]
            results_list_of_lists = await asyncio.gather(*tasks)

            # Flatten results and merge with original metadata
            flat_metadata = [meta for batch in results_list_of_lists for meta in batch]
            
            enriched_chunks = []
            for i in range(min(len(chunk_records), len(flat_metadata))):
                chunk = chunk_records[i]
                enriched_chunks.append({
                    "id": chunk["id"],
                    "user_id": user_id,
                    "job_id": job_id,
                    "document_id": chunk["source_metadata"]["document_id"],
                    "content": chunk["content"],
                    "source_metadata": chunk["source_metadata"],
                    "ai_metadata": flat_metadata[i].model_dump(),
                    "summary": flat_metadata[i].one_line_summary,
                })

            await supabase.table("ingestion_jobs").update({"status": "ai_labelled"}).eq("id", job_id).execute()

            return enriched_chunks

        except Exception as e:
            await supabase.table("ingestion_jobs").update({
                "status": "failed",
                "error_message": str(e),
            }).eq("id", job_id).execute()
            raise