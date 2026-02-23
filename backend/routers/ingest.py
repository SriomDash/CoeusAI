import os
import shutil
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.graphs.ingestion_graph import ingestion_app

ingest_router = APIRouter(prefix="/ingest", tags=["Ingestion"])

UPLOAD_ROOT = "backend/uploads"

@ingest_router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = "default_user",
    user_name: str = "Default User"
):
    job_id = str(uuid.uuid4())

    upload_dir = f"{UPLOAD_ROOT}/{job_id}"
    os.makedirs(upload_dir, exist_ok=True)

    file_path = f"{upload_dir}/{file.filename}"

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save failed: {e}")

    return {
        "status": "uploaded",
        "job_id": job_id,
        "filename": file.filename
    }


@ingest_router.post("/{job_id}/run")
async def run_ingestion(job_id: str, user_id: str = "default_user", user_name: str = "Default User"):
    upload_dir = f"{UPLOAD_ROOT}/{job_id}"
    if not os.path.isdir(upload_dir):
        raise HTTPException(status_code=404, detail="Job not found")

    # pick the first file in the job folder (or store filename explicitly)
    files = [f for f in os.listdir(upload_dir) if os.path.isfile(os.path.join(upload_dir, f))]
    if not files:
        raise HTTPException(status_code=400, detail="No uploaded file found for this job")

    file_path = os.path.join(upload_dir, files[0])

    initial_state = {
        "file_path": file_path,
        "user_id": user_id,
        "user_name": user_name,
        "job_id": job_id,
        "visuals": [],
        "text_chunks": [],
        "labeled_data": [],
        "chroma_count": 0,
        "elastic_count": 0,
        "status": "pending",
        "error": None
    }

    try:
        result = await ingestion_app.ainvoke(initial_state)

        if result["status"] == "failed":
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "status": "success",
            "job_id": job_id,
            "vectors_stored": result["chroma_count"],
            "docs_indexed": result["elastic_count"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))