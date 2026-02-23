import os
import shutil
import uuid
from fastapi import APIRouter, Request, UploadFile, File, Form, HTTPException, status
from backend.config import settings

upload_router = APIRouter(
    prefix="/upload",
    tags=["Uploads"]
)

@upload_router.post("/")
async def upload_pdf(
    request: Request,
    file: UploadFile = File(...),
    user_id: str = Form(...),
    user_name: str = Form(...)
):
    """
    Saves PDF locally and updates the Supabase users table with the job details.
    """
    # 1. Generate a Unique Job ID for this specific upload
    job_id = str(uuid.uuid4())
    
    # 2. Define and create the local directory: backend/uploads/{job_id}
    upload_dir = os.path.join("backend", "uploads", job_id)
    os.makedirs(upload_dir, exist_ok=True)
    
    file_path = os.path.join(upload_dir, file.filename)

    try:

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        supabase = request.app.state.supabase.client


        response = supabase.table("users").update({
            "user_pdf_name": file.filename,
            "job_id": job_id  
        }).eq("id", user_id).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found. Could not link PDF."
            )

        return {
            "status": "success",
            "message": "PDF uploaded and linked successfully",
            "data": {
                "job_id": job_id,
                "filename": file.filename,
                "path": file_path
            }
        }

    except Exception as e:
        if os.path.exists(upload_dir):
            shutil.rmtree(upload_dir)
        
        print(f"Upload Error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}"
        )