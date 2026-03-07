import asyncio
import instructor
from groq import AsyncGroq
from typing import List, Dict, Any

# 1. Import traceable from LangSmith
from langsmith import traceable

from backend.config import settings
from backend.models.chunkings_model import ChunkMetadata, BatchMetadata
from backend.utils.prompt_loader import load_prompt


class LabelingService:
    @staticmethod
    def _get_instructor_client():
        """
        Creates a native Groq client wrapped by Instructor.
        """
        return instructor.from_groq(
            AsyncGroq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON
        )

    @staticmethod
    @traceable(name="Labeling: LLM Batch Processing", run_type="llm") # 2. Trace the LLM execution
    async def label_batch(chunks: List[str]) -> List[ChunkMetadata]:
        """
        Processes one batch of chunk texts and returns structured metadata.
        """
        client = LabelingService._get_instructor_client()

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
            raise e

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

            if len(metadata_list) != len(chunks):
                print(f"Mismatch: Sent {len(chunks)}, got {len(metadata_list)}")

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
                ChunkMetadata(
                    keywords=[],
                    search_terms=[],
                    one_line_summary="Processing Error"
                )
                for _ in chunks
            ]

    @classmethod
    @traceable(name="Labeling: Process and Link", run_type="chain") # 3. Trace the orchestration logic
    async def process_and_link(
        cls,
        chunk_records: List[Dict[str, Any]],
        user_id: str,
        job_id: str,
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Orchestrates:
        1. Extract chunk text from structured records
        2. Batch text for LLM labeling
        3. Merge AI metadata back with original chunk metadata
        """
        if not chunk_records:
            return []

        all_chunks = [chunk["content"] for chunk in chunk_records]
        batches = [
            all_chunks[i: i + batch_size]
            for i in range(0, len(all_chunks), batch_size)
        ]

        print(f"Labeling {len(all_chunks)} chunks in {len(batches)} batches...")

        tasks = [cls.label_batch(batch) for batch in batches]
        results_list_of_lists = await asyncio.gather(*tasks)

        flat_metadata = [
            meta
            for batch in results_list_of_lists
            for meta in batch
        ]

        limit = min(len(chunk_records), len(flat_metadata))
        enriched_chunks: List[Dict[str, Any]] = []

        for i in range(limit):
            chunk = chunk_records[i]
            ai_meta = flat_metadata[i].model_dump()

            enriched_chunks.append({
                "id": chunk["id"],
                "user_id": user_id,
                "job_id": job_id,
                "document_id": chunk["source_metadata"]["document_id"],
                "content": chunk["content"],
                "source_metadata": chunk["source_metadata"],
                "ai_metadata": ai_meta,
                "summary": flat_metadata[i].one_line_summary,
            })

        return enriched_chunks