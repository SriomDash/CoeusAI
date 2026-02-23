import asyncio
import instructor
from groq import AsyncGroq
from typing import List, Dict, Any
from backend.config import settings
from backend.models.chunkings_model import ChunkMetadata, BatchMetadata
from backend.utils.prompt_loader import load_prompt

class LabelingService:
    @staticmethod
    def _get_instructor_client():
        """
        Creates a native Groq client wrapped by Instructor.
        Using from_groq instead of from_openai to avoid attribute errors.
        """
        return instructor.from_groq(
            AsyncGroq(api_key=settings.GROQ_API_KEY),
            mode=instructor.Mode.JSON
        )

    @staticmethod
    async def label_batch(chunks: List[str]) -> List[ChunkMetadata]:
        """
        Processes a batch of text chunks using Instructor to ensure valid schema.
        """
        client = LabelingService._get_instructor_client()
        
        try:
            # Load Prompts
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
            # Call LLM
            batch_result = await client.chat.completions.create(
                model=settings.GROQ_MODEL, 
                response_model=BatchMetadata,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}
                ],
                max_retries=2, 
            )
            
            # Validation: Ensure count matches input chunks
            if len(batch_result.metadata_list) != len(chunks):
                print(f"Mismatch: Sent {len(chunks)}, got {len(batch_result.metadata_list)}")
                while len(batch_result.metadata_list) < len(chunks):
                    batch_result.metadata_list.append(
                        ChunkMetadata(
                            keywords=[], 
                            search_terms=[], 
                            one_line_summary="Error: Missing generation"
                        )
                    )
            
            return batch_result.metadata_list

        except Exception as e:
            print(f"Batch Processing Failed: {e}")
            return [
                ChunkMetadata(
                    keywords=[], 
                    search_terms=[], 
                    one_line_summary="Processing Error"
                ) for _ in chunks
            ]

    @classmethod
    async def process_and_link(
        cls, 
        all_chunks: List[str], 
        user_id: str, 
        job_id: str, 
        batch_size: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Orchestrates: Batching -> AI Labeling -> Linking Data.
        """
        batches = [all_chunks[i : i + batch_size] for i in range(0, len(all_chunks), batch_size)]
        print(f"Labeling {len(all_chunks)} chunks in {len(batches)} batches...")

        # Parallel Processing
        tasks = [cls.label_batch(batch) for batch in batches]
        results_list_of_lists = await asyncio.gather(*tasks)
        
        flat_metadata = [meta for batch in results_list_of_lists for meta in batch]

        processed_data = []
        limit = min(len(all_chunks), len(flat_metadata))
        
        for i in range(limit):
            entry = {
                "user_id": user_id,
                "job_id": job_id,
                "content": all_chunks[i], 
                "metadata": flat_metadata[i].model_dump(),
                "summary": flat_metadata[i].one_line_summary 
            }
            processed_data.append(entry)

        return processed_data