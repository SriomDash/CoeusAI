from fastapi import APIRouter, UploadFile, File, Form, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from backend.schemas.models import PDFUploadModel
from backend.services.ingestion.upload_service import process_and_store_document

upload_router = APIRouter()


@upload_router.post("/api/v1/upload")
async def upload_pdf(
    user_name: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_bytes = await file.read()
        actual_size = len(file_bytes)

        await file.seek(0)

        validated_data = PDFUploadModel(
            user_name=user_name,
            file_name=file.filename,
            file_size=actual_size
        )

        result = await process_and_store_document(
            user_name=validated_data.user_name,
            file_name=validated_data.file_name,
            file_bytes=file_bytes,
            file_size=validated_data.file_size
        )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=result
        )

    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=e.errors()[0]["msg"]
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )