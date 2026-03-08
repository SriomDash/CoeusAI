from fastapi import HTTPException, status
from storage3.exceptions import StorageApiError

from backend.clients.supabase_client import supabase_bus
from backend.utils.id_generator import generate_stable_user_id, generate_file_id
from backend.utils.job_id_generator import generate_job_id
from backend.utils.file_hashing import generate_file_hash

async def process_and_store_document(
    user_name: str,
    file_name: str,
    file_bytes: bytes,
    file_size: int
) -> dict:
    # UPDATED: Get the managed client from our singleton bus
    supabase = supabase_bus.get_client()

    # 1. IDENTITY GENERATION
    user_id = generate_stable_user_id(user_name)
    document_id = generate_file_id()
    job_id = generate_job_id()
    file_hash = generate_file_hash(file_bytes)

    # 2. USER UPSERT (Ensures user exists without duplication)
    await supabase.table("users").upsert({
        "id": user_id,
        "user_name": user_name.strip()
    }).execute()

    # 3. DEDUPLICATION CHECK (Content-based hashing)
    duplicate_check = (
        await supabase.table("documents")
        .select("id")
        .eq("file_hash", file_hash)
        .eq("user_id", user_id)
        .execute()
    )

    if duplicate_check.data and len(duplicate_check.data) > 0:
        existing_document_id = duplicate_check.data[0]["id"]

        # Find the latest job for this specific file
        existing_job_result = (
            await supabase.table("ingestion_jobs")
            .select("id, status, created_at")
            .eq("user_id", user_id)
            .eq("document_id", existing_document_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if existing_job_result.data and len(existing_job_result.data) > 0:
            existing_job_id = existing_job_result.data[0]["id"]
            existing_job_status = existing_job_result.data[0]["status"]
        else:
            # Fallback if doc exists but job was lost
            existing_job_id = generate_job_id()
            existing_job_status = "uploaded"
            await supabase.table("ingestion_jobs").insert({
                "id": existing_job_id,
                "user_id": user_id,
                "document_id": existing_document_id,
                "status": "uploaded"
            }).execute()

        # Route the user: If done, go to Chat. If not, continue processing.
        next_stage = "querying" if existing_job_status == "done" else "resume_ingestion"

        return {
            "message": "This exact file has already been uploaded.",
            "already_exists": True,
            "document_id": existing_document_id,
            "user_id": user_id,
            "job_id": existing_job_id,
            "job_status": existing_job_status,
            "next_stage": next_stage,
        }

    # 4. STORAGE UPLOAD (Only runs if file is unique)
    storage_path = f"{user_id}/{document_id}.pdf"

    try:
        await supabase.storage.from_("raw_documents").upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
    except StorageApiError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supabase storage upload failed: {str(e)}"
        )

    # 5. DATABASE RECORDING (Finalizing the state)
    await supabase.table("documents").insert({
        "id": document_id,
        "user_id": user_id,
        "file_name": file_name,
        "file_hash": file_hash,
        "file_size_bytes": file_size,
        "storage_path": storage_path,
        "status": "uploaded"
    }).execute()

    await supabase.table("ingestion_jobs").insert({
        "id": job_id,
        "user_id": user_id,
        "document_id": document_id,
        "status": "uploaded"
    }).execute()

    return {
        "message": "File uploaded and job created successfully.",
        "already_exists": False,
        "document_id": document_id,
        "user_id": user_id,
        "job_id": job_id,
        "job_status": "uploaded",
        "next_stage": "resume_ingestion",
    }