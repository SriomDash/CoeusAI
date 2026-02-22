from supabase import create_client
from backend.config import settings

class SupabaseClient:
    def __init__(self):
        self.client = create_client(
            settings.SUPABASE_URL, 
            settings.SUPABASE_SERVICE_ROLE_KEY
        )

supabase_bus = SupabaseClient()