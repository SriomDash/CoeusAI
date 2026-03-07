import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException

from backend.graphs.ingestion_graph import ingestion_app
from backend.services.pdf_service import PDFService
from backend.services.ingestion_tracking_service import IngestionTrackingService

ingest_router = APIRouter(prefix="/ingest", tags=["Ingestion"])

UPLOAD_ROOT = "backend/uploads"


@ingest_router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = "",
    user_name: str = ""
):
    """
    Upload only saves the file and returns an upload_id.
    No job_id is created here.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not user_name:
        raise HTTPException(status_code=400, detail="user_name is required")

    upload_id = str(uuid.uuid4())

    upload_dir = os.path.join(UPLOAD_ROOT, upload_id)
    os.makedirs(upload_dir, exist_ok=True)

    file_path = os.path.join(upload_dir, file.filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    return {
        "status": "uploaded",
        "upload_id": upload_id,
        "filename": file.filename,
        "user_id": user_id,
        "user_name": user_name
    }


@ingest_router.post("/{upload_id}/run")
async def run_ingestion(
    upload_id: str,
    user_id: str = "",
    user_name: str = ""
):
    """
    Processing starts here.
    job_id is created here, tightly coupled to user_id + document processing run.
    """
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")
    if not user_name:
        raise HTTPException(status_code=400, detail="user_name is required")

    upload_dir = os.path.join(UPLOAD_ROOT, upload_id)
    if not os.path.isdir(upload_dir):
        raise HTTPException(status_code=404, detail="Upload not found")

    files = [
        f for f in os.listdir(upload_dir)
        if os.path.isfile(os.path.join(upload_dir, f))
    ]
    if not files:
        raise HTTPException(status_code=400, detail="No uploaded file found for this upload")

    file_path = os.path.join(upload_dir, files[0])
    source_name = files[0]

    try:
        with open(file_path, "rb") as f:
            content = f.read()

        document_id = PDFService.generate_document_id(content)
        file_size = len(content)
        job_id = str(uuid.uuid4())

        IngestionTrackingService.upsert_document(
            user_id=user_id,
            document_id=document_id,
            source_name=source_name,
            file_path=file_path,
            file_size=file_size,
            status="uploaded",
            last_job_id=job_id,
        )

        IngestionTrackingService.create_job(
            job_id=job_id,
            user_id=user_id,
            document_id=document_id,
            source_name=source_name,
            status="queued",
        )

        IngestionTrackingService.update_document_status(
            user_id=user_id,
            document_id=document_id,
            status="processing",
            last_job_id=job_id,
        )

        IngestionTrackingService.update_job_status(
            job_id=job_id,
            status="extracting",
        )

        initial_state = {
            "file_path": file_path,
            "user_id": user_id,
            "user_name": user_name,
            "job_id": job_id,
            "document_id": document_id,
            "pages": [],
            "chunk_records": [],
            "enriched_chunks": [],
            "chroma_count": 0,
            "elastic_count": 0,
            "status": "pending",
            "error": None,
            "error_stage": None,
        }

        result = await ingestion_app.ainvoke(initial_state)

        if result["status"] == "failed":
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "status": "success",
            "upload_id": upload_id,
            "job_id": job_id,
            "document_id": document_id,
            "vectors_stored": result["chroma_count"],
            "docs_indexed": result["elastic_count"]
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))