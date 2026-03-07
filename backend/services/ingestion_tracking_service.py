from typing import Optional
from backend.clients.supabase_client import get_supabase_client


class IngestionTrackingService:
    @staticmethod
    def upsert_document(
        user_id: str,
        document_id: str,
        source_name: str,
        file_path: Optional[str] = None,
        file_size: Optional[int] = None,
        mime_type: str = "application/pdf",
        status: str = "uploaded",
        last_job_id: Optional[str] = None,
        total_pages: int = 0,
        total_chunks: int = 0,
    ) -> None:
        client = get_supabase_client()

        payload = {
            "user_id": user_id,
            "document_id": document_id,
            "source_name": source_name,
            "file_path": file_path,
            "file_size": file_size,
            "mime_type": mime_type,
            "status": status,
            "last_job_id": last_job_id,
            "total_pages": total_pages,
            "total_chunks": total_chunks,
        }

        client.table("documents").upsert(
            payload,
            on_conflict="user_id,document_id"
        ).execute()

    @staticmethod
    def update_document_status(
        user_id: str,
        document_id: str,
        status: str,
        last_job_id: Optional[str] = None,
        total_pages: Optional[int] = None,
        total_chunks: Optional[int] = None,
    ) -> None:
        client = get_supabase_client()

        payload = {
            "status": status,
        }

        if last_job_id is not None:
            payload["last_job_id"] = last_job_id
        if total_pages is not None:
            payload["total_pages"] = total_pages
        if total_chunks is not None:
            payload["total_chunks"] = total_chunks

        client.table("documents") \
            .update(payload) \
            .eq("user_id", user_id) \
            .eq("document_id", document_id) \
            .execute()

    @staticmethod
    def create_job(
        job_id: str,
        user_id: str,
        document_id: str,
        source_name: str,
        status: str = "queued",
    ) -> None:
        client = get_supabase_client()

        client.table("ingestion_jobs").insert({
            "id": job_id,
            "user_id": user_id,
            "document_id": document_id,
            "source_name": source_name,
            "status": status,
        }).execute()

    @staticmethod
    def update_job_status(
        job_id: str,
        status: str,
        error_stage: Optional[str] = None,
        error_message: Optional[str] = None,
        extracted_pages: Optional[int] = None,
        extracted_chunks: Optional[int] = None,
        chroma_count: Optional[int] = None,
        elastic_count: Optional[int] = None,
        completed: bool = False,
    ) -> None:
        client = get_supabase_client()

        payload = {
            "status": status,
        }

        if error_stage is not None:
            payload["error_stage"] = error_stage
        if error_message is not None:
            payload["error_message"] = error_message
        if extracted_pages is not None:
            payload["extracted_pages"] = extracted_pages
        if extracted_chunks is not None:
            payload["extracted_chunks"] = extracted_chunks
        if chroma_count is not None:
            payload["chroma_count"] = chroma_count
        if elastic_count is not None:
            payload["elastic_count"] = elastic_count
        if completed:
            payload["completed_at"] = "now()"

        client.table("ingestion_jobs") \
            .update(payload) \
            .eq("id", job_id) \
            .execute()