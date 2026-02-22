from fastapi import APIRouter, Request, HTTPException, status
from backend.models.users_model import UserCreate

user_router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@user_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_user(request: Request, user_data: UserCreate):
    """
    Stores a new user in the Supabase 'users' table.
    """
    try:
       
        supabase = request.app.state.supabase.client
        
        response = supabase.table("users").insert({
            "user_name": user_data.user_name,
            "user_pdf_name": user_data.user_pdf_name
        }).execute()

        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user record."
            )

        return {
            "message": "User created successfully",
            "user": response.data[0]
        }

    except Exception as e:
        print(f"Error inserting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while saving user data."
        )