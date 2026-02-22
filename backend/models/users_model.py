from pydantic import BaseModel
from typing import Optional

class UserCreate(BaseModel):
    user_name: str
    user_pdf_name: Optional[str] = None