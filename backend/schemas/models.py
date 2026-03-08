from pydantic import BaseModel, field_validator

class PDFUploadModel(BaseModel):
    user_name: str
    file_name: str
    file_size: int  

    # 1. Validate the file extension
    @field_validator('file_name')
    @classmethod
    def validate_extension(cls, value: str) -> str:
        if not value.lower().endswith('.pdf'):
            raise ValueError("Invalid file format. Only .pdf files are allowed.")
        return value

    # 2. Validate the file size (Max 10MB)
    @field_validator('file_size')
    @classmethod
    def validate_size(cls, value: int) -> int:
        max_size = 10 * 1024 * 1024  # 10 MB in bytes
        if value > max_size:
            raise ValueError(f"File size exceeds the 10MB limit. Current size: {value} bytes.")
        return value
    
    
class IngestRequestModel(BaseModel):
    user_id: str
    job_id: str
    document_id: str