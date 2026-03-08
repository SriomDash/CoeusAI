from typing import Dict, Any
# UPDATED: Use the Bus Singleton
from backend.clients.supabase_client import supabase_bus

class IngestionFinalizerServiceError(Exception): pass
class InvalidJobStateError(IngestionFinalizerServiceError): pass
class JobNotFoundError(IngestionFinalizerServiceError): pass

class IngestionFinalizerService:
    @staticmethod
    async def _get_job(user_id: str, job_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus
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
            raise JobNotFoundError(
                f"No ingestion job found for job_id={job_id} and user_id={user_id}"
            )

        return job_result.data[0]

    @classmethod
    async def finalize_job(cls, user_id: str, job_id: str) -> Dict[str, Any]:
        # UPDATED: Use the bus
        supabase = supabase_bus.get_client()
        job = await cls._get_job(user_id=user_id, job_id=job_id)

        # 1. State Guard: Ensure the previous step (Elasticsearch) actually finished
        if job["status"] != "keyword_inserted":
            raise InvalidJobStateError(
                f"Job {job_id} is in status '{job['status']}'. Expected 'keyword_inserted'."
            )

        try:
            # 2. Update the Job Record to 'done'
            await supabase.table("ingestion_jobs").update(
                {"status": "done"}
            ).eq("id", job_id).eq("user_id", user_id).execute()

            # 3. Update the Document Record to 'done'
            # PRO TIP: The 'documents' table is what your chat UI likely checks.
            # Marking this as 'done' allows the file to show up in the user's library.
            await supabase.table("documents").update(
                {"status": "done"}
            ).eq("id", job["document_id"]).eq("user_id", user_id).execute()

            return {
                "user_id": user_id,
                "job_id": job_id,
                "document_id": job["document_id"],
                "status": "done",
            }

        except Exception as e:
            # If finalization fails, we don't mark as 'done' to prevent users
            # from querying a potentially incomplete index.
            raise IngestionFinalizerServiceError(
                f"Failed to finalize ingestion job {job_id}: {str(e)}"
            ) from e