import logging
from supabase import create_async_client, AsyncClient
from backend.config import settings

logger = logging.getLogger("coeus_ai.supabase_bus")

class SupabaseBus:
    def __init__(self):
        self.client: AsyncClient | None = None

    async def connect(self):
        """
        Initializes the Supabase client and verifies the connection with a quick query.
        """
        if self.client:
            return  

        try:
            logger.info("Connecting to Supabase...")
            
            self.client = await create_async_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SECRET_KEY,
            )

            await self.client.table("users").select("id").limit(1).execute()
            logger.info("Supabase Connected and Verified Successfully.")

        except Exception as e:
            logger.error(f"Supabase Connection/Verification Failed: {e}")
            self.client = None  
            raise e

    async def close(self):
        """
        Supabase-py handles most cleanup, but we nullify the reference
        to ensure a clean state for testing/restarts.
        """
        if self.client:
            logger.info("Supabase Connection Reference Cleared.")
            self.client = None

    def get_client(self) -> AsyncClient:
        """
        Returns the active client. Raises error if not initialized.
        """
        if not self.client:
            raise RuntimeError("Supabase client is not initialized. Call connect() first.")
        return self.client

# Singleton Instance
supabase_bus = SupabaseBus()