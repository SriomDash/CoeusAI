import re
import uuid

from fastapi import APIRouter, HTTPException, status
from backend.schemas.users_model import UserCreate
from backend.clients.supabase_client import get_supabase_client

user_router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


def slugify_name(name: str) -> str:
    value = name.strip().lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^a-z0-9_]", "", value)
    return value or "user"


def generate_user_id(user_name: str) -> str:
    base = slugify_name(user_name)
    short_suffix = uuid.uuid4().hex[:8]
    return f"{base}_{short_suffix}"


@user_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(user_data: UserCreate):
    """
    Receives only user_name.
    Backend generates user_id, stores the user,
    and returns the created user for frontend tracing.
    """
    try:
        supabase = get_supabase_client()

        user_id = generate_user_id(user_data.user_name)

        payload = {
            "id": user_id,
            "user_name": user_data.user_name,
            "user_pdf_name": user_data.user_pdf_name,
        }

        response = supabase.table("users").insert(payload).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user record."
            )

        return {
            "message": "User created successfully",
            "user": {
                "user_id": user_id,
                "user_name": user_data.user_name,
                "user_pdf_name": user_data.user_pdf_name,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while saving user data."
        )