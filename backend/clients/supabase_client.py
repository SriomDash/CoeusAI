from supabase import create_client, Client
from backend.config import settings


_supabase: Client | None = None


def get_supabase_client() -> Client:
    global _supabase

    if _supabase is None:
        _supabase = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY,
        )

    return _supabase